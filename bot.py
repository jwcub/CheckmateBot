import random
import re
from time import sleep
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
import datetime
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.ocr.v20181119 import ocr_client, models
import base64
import requests
import threading

from map import *
from database import *


class Bot(object):

    def __init__(self):
        self.kanaLink = "https://kana.byha.top:444/"

        config = json.load(open("config.json", 'r'))

        self.username = config['username']  # 用户名
        self.password = config['password']  # 密码
        self.roomId = config['roomID']  # 房间号
        self.isSecret = False
        self.isAutoReady = True
        self.mp = Map()  # 地图
        self.data = DataBase()  # 数据库
        self.isAutoSave = False
        self.selectedMap = '1'
        self.ondefend = False
        self.controller = config['controller']
        self.secretId = config['secretId']
        self.secretKey = config['secretKey']
        self.userCount = 2
        self.colortousername = {}

        self.commands = {'help (command)': '查看命令列表（或命令command的用法）',
                         'query (i)': '查询自己（或玩家i）的用户信息',
                         'info': '获取Rating排行榜前10名', 'predict (i)': '预测自己（或房内玩家i）下局Rating变化'}
        self.aToB = {'help': 'help (command)', 'info': 'info', 'query': 'query (i)', 'predict': 'predict (i)'}
        self.tips = ['Bot会智能守家', '<del>杀死Bot的次数越多越容易触发特异性打击</del>', '<del>Bot已参战</del>', '<del>如果没有足够实力请不要与Bot单挑</del>',
                     '<del>输入INFO可以获取实力排行榜</del>']
        tmp = list(self.commands.keys())
        for x in tmp:
            self.tips.append('命令' + x + ': ' + self.commands[x])

    def SendKeyToTable(self, key):
        ac = ActionChains(self.driver)
        ac.send_keys(key).perform()

    def EnterRoom(self):  # 进入房间
        self.driver.get(
            "https://kana.byha.top:444/checkmate/room/" + self.roomId)
        if self.isSecret:
            settingBtn = self.driver.find_element_by_class_name(
                "form-check-input")
            ac = ActionChains(self.driver)
            ac.click(settingBtn).perform()
        print("Bot已就位！")
        self.url = self.driver.current_url

    def GetMap(self):  # 获得地图
        try:
            s = self.driver.find_element_by_id("m").get_attribute("innerHTML")
        except:
            return
        stype = []
        stmp = []
        cnt = 0
        while True:
            tmp = re.search(r'class="[\s\S]*?"', s)
            if tmp:
                g = tmp.group()
                g = g[7:len(g) - 1]
                stype.append(" " + g + " ")
                p = s.find(g)
                s = s[p + len(g):len(s)]
                cnt += 1
            else:
                break
            tmp = re.search(r'>.*?<', s)
            g = tmp.group()
            g = g[1:len(g) - 1]
            stmp.append(g)
        self.mp.resize(int(cnt ** 0.5))
        if not (self.mp.size == 9 or self.mp.size == 10 or self.mp.size == 19 or self.mp.size == 20):
            return
        if len(self.colortousername) > 0:
            c = list(self.colortousername.keys())
        for i in range(1, self.mp.size + 1):
            for j in range(1, self.mp.size + 1):
                p = stype[0]
                stype.pop(0)
                if p.find(" city ") != -1:
                    self.mp.mp[i][j].type = 'city'
                elif p.find(' empty-city ') != -1:
                    self.mp.mp[i][j].type = 'empty-city'
                elif p.find(" crown ") != -1:
                    self.mp.mp[i][j].type = 'general'
                elif p.find(" mountain ") != -1 or p.find(" obstacle ") != -1 or p.find(" gas ") != -1:
                    self.mp.mp[i][j].type = 'mountain'
                elif p.find(" null ") != -1 and p.find(" grey ") == -1:
                    self.mp.mp[i][j].type = 'land'
                elif p.find(" null ") != -1 and p.find(" grey ") != -1:
                    self.mp.mp[i][j].type = 'empty'
                else:
                    self.mp.mp[i][j].type = 'unknown'
                if p.find(" own ") != -1:
                    self.mp.mp[i][j].belong = 1
                elif self.mp.mp[i][j].type == 'land' or self.mp.mp[i][j].type == 'general' or self.mp.mp[i][
                    j].type == 'city' and len(self.colortousername) > 0:
                    for k in c:
                        if p.find(' ' + k + ' ') != -1:
                            self.mp.mp[i][j].belong = self.colortousername[k]
                            break
                if self.mp.mp[i][j].belong == 0:
                    self.mp.mp[i][j].belong = 'undefined'
                p = stmp[0]
                stmp.pop(0)
                try:
                    self.mp.mp[i][j].tmp = int(p)
                except:
                    self.mp.mp[i][j].tmp = 0
        return

    def GetMessage(self):  # 获取消息
        try:
            s = self.driver.find_element_by_id("msg-container").get_attribute("innerHTML")
        except:
            self.EnterRoom()
            return
        self.msg = []
        while True:
            tmp = re.search(r'<p>[\s\S]*?</p>', s)
            if tmp:
                g = tmp.group()
                g = re.sub(r'&nbsp;', '', g)
                g = g[3:len(g) - 4]
                p = g.find(':')
                self.msg.append([g[0:p], g[p + 2:len(g)]])
                p = s.find(g)
                s = s[p + len(g):len(s)]
            else:
                break
        return

    def SelectLand(self, x, y):  # 选择土地
        try:
            self.driver.find_element_by_id(
                "td-" + str((x - 1) * self.mp.size + y)).click()
            self.curx = x
            self.cury = y
            return
        except:
            return

    def CommandLine(self):  # 命令行
        while True:
            sleep(0.3)
            if not self.On:
                return
            self.GetMessage()
            cur = self.msg[len(self.msg) - 1]
            tmp = ['']
            tot = 0
            for i in range(0, len(cur[1])):
                if cur[1][i] == ' ' and (i == 0 or cur[1][i - 1] != ' '):
                    tot += 1
                    tmp.append('')
                elif cur[1][i] != ' ':
                    tmp[tot] += cur[1][i]
            if tmp[0] in list(self.aToB.keys()) and self.data.getByKey(cur[0], 'ban') > 0:
                self.sendMessage('您已被封禁，剩余' + str(self.data.getByKey(cur[0], 'ban')) + '天')
                continue
            if tmp[0] == 'help':
                if tot == 0:
                    msg = '<strong>命令列表：</strong><br>'
                    tmp = list(self.aToB.keys())
                    for x in tmp:
                        msg += x + ', '
                    self.sendMessage(msg)
                    self.sendMessage('提示：输入help [command]以查询命令command的用法')
                elif tot == 1:
                    try:
                        x = self.aToB[tmp[1]]
                        self.sendMessage('命令' + x + ': ' + self.commands[x])
                    except:
                        self.sendMessage('未找到该命令')
                else:
                    self.sendMessage('需要0或1个参数，发现' + str(tot) + '个')
            if tmp[0] == 'query':
                uname = ''
                if tot != 0 and tot != 1:
                    self.sendMessage('需要0或1个参数，发现' + str(tot) + '个')
                elif tot == 0:
                    uname = cur[0]
                elif tot == 1:
                    uname = tmp[1]
                if uname != '':
                    self.sendMessage('Rating: ' + str(self.data.getByKey(uname, 'Rating')) + '<br>'
                                     + '单挑胜利次数: ' + str(self.data.getByKey(uname, 'wintime')) + '<br>' +
                                     '剩余封禁天数: ' + str(self.data.getByKey(uname, 'ban')) + '<br>' +
                                     '最近Rating更新时间: ' + str(
                        int(time.time() - self.data.getByKey(uname, 'lastratingupdated'))) + '秒前<br>')
            if tmp[0] == 'info':
                uname = self.data.getUserNameList()
                winners = '<strong>Rating排行榜：</strong><br>'
                winnerList = []
                cmp = lambda s1: s1[1]
                for i in uname:
                    uid = self.GetUidByUsername(i)
                    if time.time() - self.data.getByKey(i, 'lastratingupdated') < 604800 and (
                            self.GetUserInfoByUid(uid)['bili_uid'] != 0 or self.GetUserLevelByUid(uid) >= 6):
                        winnerList.append([i, self.data.getByKey(i, 'Rating')])
                winnerList.sort(key=cmp, reverse=True)
                cnt = 0
                for i in winnerList:
                    winners += '#' + str(cnt + 1) + ',' + i[0] + ':' + str(i[1]) + '<br>'
                    if len(winners) >= 70:
                        self.sendMessage('<br>' + winners)
                        winners = ''
                    cnt += 1
                    if cnt >= 10:
                        break
                if winners != '':
                    self.sendMessage('<br>' + winners)
            if tmp[0] == 'predict':
                if tot == 0:
                    curuser = cur[0]
                elif tot == 1:
                    curuser = tmp[1]
                else:
                    self.sendMessage('需要0或1个参数，发现' + str(tot) + '个')
                    continue
                user = self.getUserInRoom()
                if curuser not in user:
                    self.sendMessage('玩家不在房间中')
                    continue
                winner = curuser
                firstAmount = 0
                firstRating = -1
                firstBounce = 0
                for j in user:
                    if j == winner:
                        firstAmount += 1
                        firstRating = max(firstRating, self.data.getByKey(j, 'Rating'))
                for k in user:
                    if k == winner:
                        continue
                    score = round((self.data.getByKey(k, 'Rating') - firstRating) / 1000) + 3
                    if score <= 0:
                        score = 1
                    if score > 10:
                        score = 10
                    firstBounce += score
                WinRating = self.changeRating(winner, firstBounce / firstAmount, self.data.getByKey(winner, 'Rating'),
                                              True)
                MaxLoseRating = -99999
                MinLoseRating = 99999
                AvgLoseRating = 0
                for winner in user:
                    if winner == curuser:
                        continue
                    firstAmount = 0
                    firstRating = -1
                    firstBounce = 0
                    for j in user:
                        if j == winner:
                            firstAmount += 1
                            firstRating = max(firstRating, self.data.getByKey(j, 'Rating'))
                    k = curuser
                    score = round((self.data.getByKey(k, 'Rating') - firstRating) / 1000) + 3
                    if score <= 0:
                        score = 1
                    if score > 10:
                        score = 10
                    firstBounce += score
                    currating = self.changeRating(k, -score, self.data.getByKey(k, 'Rating'), True)
                    MaxLoseRating = max(currating, MaxLoseRating)
                    MinLoseRating = min(MinLoseRating, currating)
                    AvgLoseRating += currating
                AvgLoseRating //= len(user) - 1
                y = -AvgLoseRating / WinRating
                self.sendMessage('<br>Win:' + str(WinRating) + '<br>Lose:' + str(MinLoseRating) + '~' + str(
                    MaxLoseRating) + ', Avg.' + str(AvgLoseRating) + '<br>推荐胜率：' + str(
                    round(100 / (y + 1) * y, 1)) + '%')

            if tmp[0] == 'kill':
                if cur[0] == self.controller:
                    self.driver.close()
                    del self
                else:
                    self.sendMessage('权限不足')
            if tmp[0] == 'enter':
                if cur[0] == self.controller:
                    self.roomId = tmp[1]
                    self.EnterRoom()
                else:
                    self.sendMessage('权限不足')
            if tmp[0] == 'setsecret':
                if cur[0] == self.controller:
                    self.isSecret = not self.isSecret
                    self.sendMessage('secret = ' + str(self.isSecret))
                else:
                    self.sendMessage('权限不足')
            if tmp[0] == 'savedata':
                if cur[0] == self.controller:
                    self.data.saveData()
                    self.sendMessage('saved')
                else:
                    self.sendMessage('权限不足')
            if tmp[0] == 'readdata':
                if cur[0] == self.controller:
                    try:
                        self.data.readData()
                        self.sendMessage('read')
                    except:
                        self.sendMessage('error')
                else:
                    self.sendMessage('权限不足')
            if tmp[0] == 'setdata':
                if cur[0] == self.controller:
                    self.data.setByKey(tmp[1], int(tmp[3]), tmp[2])
                    self.sendMessage(tmp[2] + ' = ' + tmp[3])
                else:
                    self.sendMessage('权限不足')
        return

    def Logout(self):  # 登出
        print('正在登出…')
        self.driver.get('https://kana.byha.top:444/logout')
        self.driver.switch_to.default_content()
        sleep(5)
        self.driver.find_element_by_id('submitButton').click()
        return

    def delNode(self, a):
        self.driver.execute_script("""
                                   var element = arguments[0];
                                     element.parentNode.removeChild(element);
                                     """, a)
        return

    def Login(self):  # 登录
        print("正在登录…")
        self.driver.get(self.kanaLink)
        usernameBox = self.driver.find_element_by_name("username")
        passwordBox = self.driver.find_element_by_name("pwd")

        ac = ActionChains(self.driver)
        ac.send_keys_to_element(usernameBox, self.username)
        ac.send_keys_to_element(passwordBox, self.password).perform()
        # self.delNode(self.driver.find_element_by_css_selector('[rel="stylesheet"]'))
        while True:
            if self.driver.current_url == self.kanaLink:
                break
            self.driver.execute_script('document.getElementById("cap").childNodes[1].style.width="150%"')
            frame = self.driver.find_element_by_xpath('/html/body/div[2]/div/form/div[1]/object')
            self.driver.switch_to.frame(frame)
            try:
                a = self.driver.find_element_by_css_selector('[fill="none"]')
                self.delNode(a)
            except:
                sleep(1)
                continue

            self.driver.switch_to.default_content()

            cap = -1
            self.driver.get_screenshot_as_file('a.png')

            try:
                cred = credential.Credential(self.secretId, self.secretKey)
                httpProfile = HttpProfile()
                httpProfile.endpoint = "ocr.tencentcloudapi.com"

                clientProfile = ClientProfile()
                clientProfile.httpProfile = httpProfile
                client = ocr_client.OcrClient(cred, "ap-shanghai", clientProfile)

                req = models.GeneralBasicOCRRequest()
                params = {
                    "ImageBase64": base64.b64encode(open('a.png', 'rb').read()).decode()
                }
                req.from_json_string(json.dumps(params))

                resp = client.GeneralBasicOCR(req)
                a = json.loads(resp.to_json_string())

            except TencentCloudSDKException as err:
                print(err)
            for i in a['TextDetections']:
                tmp = i['DetectedText']
                s = ''
                for j in tmp:
                    if j != '(' and j != ')':  # 去除诡异括号
                        s += j
                tmp = s
                if re.match(r'\w\w\w\w', tmp) and len(tmp) == 4:
                    cap = tmp
                    break
            print(cap)
            ac = ActionChains(self.driver)
            ac.send_keys_to_element(self.driver.find_element_by_name("cap"), cap).perform()
            self.driver.find_element_by_id("submitButton").click()
            try:
                WebDriverWait(self.driver, 10).until(EC.url_to_be(self.kanaLink))
                break
            except TimeoutException:
                pass
        print("登录成功！")
        return

    def moveTo(self, x, y):  # 移动
        path, cost = self.mp.findPath(self.curx, self.cury, x, y)
        if path:
            path.pop(0)
            cx = self.curx
            cy = self.cury
            while path:
                px = path[0][0]
                py = path[0][1]
                if cx < px and cy == py:
                    self.movements.append('S')
                elif cx > px and cy == py:
                    self.movements.append('W')
                elif cx == px and cy > py:
                    self.movements.append('A')
                else:
                    self.movements.append('D')
                cx = px
                cy = py
                path.pop(0)
        return

    def flushMovements(self):  # 更新移动
        tmp = self.mp.mp[self.homex][self.homey].tmp
        self.SendKeyToTable(self.movements[0])
        if self.mp.mp[self.curx][self.cury].belong != 1:
            self.movements = []
            return
        if self.movements[0] == 'W':
            self.curx -= 1
        elif self.movements[0] == 'S':
            self.curx += 1
        elif self.movements[0] == 'A':
            self.cury -= 1
        else:
            self.cury += 1
        self.movements.pop(0)
        self.GetMap()
        self.updateMap()
        trytime = 0
        while self.mp.mp[self.homex][self.homey].tmp == tmp and trytime <= 80:
            self.GetMap()
            trytime += 1
        return

    def pre(self):  # 预处理地图
        tmp = self.mp.findMatch(lambda a: a.type == 'general' and a.belong == 1)
        if len(tmp) != 1:
            return 1
        self.homex = tmp[0][0]
        self.homey = tmp[0][1]
        self.curx = self.homex
        self.cury = self.homey
        self.movements = []
        self.homes = []
        self.vis = []
        self.ispre = True  # 是否预处理
        self.useless = []
        self.preland = []

        self.colortousername = {}
        a = self.driver.find_element_by_id('info-content').get_attribute('innerHTML')
        while True:  # 读取领地-兵力排行榜
            p1 = a.find(':')
            p2 = a.find(';')
            if p1 == -1 or p2 == -1:
                break
            color = a[p1 + 2:p2]
            a = a[p2 + 1:]
            p1 = a.find('>')
            p2 = a.find('<')
            username = a[p1 + 1:p2]
            self.colortousername[color] = username
        return 0

    def sendMessage(self, msg):  # 发送消息
        if len(msg) >= 92:
            self.sendMessage(msg[0:90])
            self.sendMessage(msg[90:len(msg)])
        messageBox = self.driver.find_element_by_id("msg-sender")
        ac = ActionChains(self.driver)
        ac.send_keys_to_element(messageBox, msg)
        ac.send_keys(Keys.ENTER).perform()
        return

    def updateMap(self):  # 分析地图
        tmp = self.mp.findMatch(lambda a: a.type == 'general' and a.belong != 1)
        if tmp:
            for i in tmp:
                if i not in self.homes:  # 找家
                    self.homes.append(i)
        tmp = self.mp.findMatch(lambda a: a.type != 'unknown')
        for i in tmp:
            if i not in self.vis:  # 已经可见的土地无需探索
                self.vis.append(i)
        if not self.preland:
            self.preland = self.mp.findMatch(lambda a: a.type == 'empty' or a.belong == 1)
        else:
            enemy = self.mp.findMatch(lambda a: a.belong != 1)
            for i in enemy:
                if i in self.preland and i not in self.useless:  # 之前是空地或己方土地，现在是敌方土地，无需探索
                    self.useless.append(i)
            self.preland = []
        return

    def botMove(self):  # 主循环，每回合执行一次
        self.GetMap()
        if not self.ispre:
            if self.pre() == 1:
                return
        if self.movements:
            self.flushMovements()
            return
        if [self.curx, self.cury] in self.homes and self.mp.mp[self.curx][self.cury].belong == 1:  # 已经占领的家移除
            self.homes.remove([self.curx, self.cury])
        if [self.curx, self.cury] not in self.vis:
            self.vis.append([self.curx, self.cury])
        self.updateMap()
        mx = self.mp.findMax(lambda a: a.belong == 1)
        if self.mp.mp[mx[0]][mx[1]].tmp <= 5:
            return
        if self.homes:  # 智能掏家
            if self.mp.mp[mx[0]][mx[1]].tmp > 30 and self.mp.mp[mx[0]][mx[1]].type == 'general':
                tmp = self.mp.findMax(lambda a: a.type != 'general' and a.belong == 1)
                if self.mp.mp[tmp[0]][tmp[1]].tmp * 3 > self.mp.mp[mx[0]][mx[1]].tmp:
                    mx = tmp
            self.SelectLand(mx[0], mx[1])
            tmp = random.choice(self.homes)
            self.moveTo(tmp[0], tmp[1])
            return
        tmp = self.mp.findMatchByRange(self.homex, self.homey, 1,
                                       lambda a: a.belong != 1 and (a.type == 'land' or a.type == 'city'))
        if tmp and self.mp.mp[mx[0]][mx[1]].tmp > 30:  # 智能守家
            mx = self.mp.findMax(lambda a: a.type != 'general' and a.belong == 1)
            self.SelectLand(mx[0], mx[1])
            tmp = random.choice(tmp)
            self.moveTo(tmp[0], tmp[1])
            self.ondefend = True
            return
        if self.ondefend and dist(self.curx, self.cury, self.homex, self.homey) <= 2:
            self.moveTo(self.homex, self.homey)
            self.ondefend = False
            return
        self.ondefend = False
        tmp = self.mp.findMatch(lambda a: a.type == 'unknown')
        random.shuffle(tmp)
        role = lambda a: len(self.mp.findMatchByRange(a[0], a[1], 4, lambda b: b.type == 'land' and b.belong != 1 and (
                a not in self.useless)))
        tmp.sort(key=role, reverse=True)
        for i in tmp:
            if [i[0], i[1]] not in self.vis:
                target = i
                break
        owned = self.mp.findMatch(lambda a: a.belong == 1 and a.tmp >= self.mp.mp[target[0]][target[1]].tmp)
        if not owned:
            owned = [[self.homex, self.homey]]
        random.shuffle(owned)
        mindist = 10000
        ans = []
        for i in owned:
            p = dist(i[0], i[1], target[0], target[1])
            if p < self.mp.mp[i[0]][i[1]].tmp and p < mindist:
                path, cost = self.mp.findPath(self.curx, self.cury, target[0], target[1])
                if self.mp.mp[i[0]][i[1]].tmp >= cost:
                    mindist = p
                    ans = i
        if ans:  # 探索
            if ans[0] == self.homex and ans[1] == self.homey:
                self.SendKeyToTable('Z')
            self.SelectLand(ans[0], ans[1])
            self.moveTo(target[0], target[1])
        return

    def changeRating(self, username, rating, nowRating, predict=False):
        if rating > 0:
            rating = round(rating * (abs(49.5 - 0.01 * nowRating) + 50.5 - 0.01 * nowRating) / 10)
        else:
            rating = rating * round(0.002 * nowRating + 1)
        if predict:
            return rating
        if nowRating >= 0 and nowRating + rating < 0:
            self.data.setByKey(username, 0, 'Rating')
        else:
            self.data.addByKey(username, rating, 'Rating')
        self.data.setByKey(username, time.time(), 'lastratingupdated')
        return

    def gameRatingCalc(self, winner):
        user = []
        tmp = list(self.colortousername.keys())
        for i in tmp:
            user.append(self.colortousername[i])
        firstAmount = 0
        firstRating = -1
        firstBounce = 0
        for j in user:
            if j == winner:
                firstAmount += 1
                firstRating = max(firstRating, self.data.getByKey(j, 'Rating'))
        for k in user:
            if k == winner:
                continue
            score = round((self.data.getByKey(k, 'Rating') - firstRating) / 1000) + 3
            if score <= 0:
                score = 1
            if score > 10:
                score = 10
            firstBounce += score
            self.changeRating(k, -score, self.data.getByKey(k, 'Rating'));
        self.changeRating(winner, firstBounce / firstAmount, self.data.getByKey(winner, 'Rating'))
        return

    def updateData(self):  # 每日一次
        uname = self.data.getUserNameList()
        for i in uname:
            if self.data.getByKey(i, 'wintime') > 0:
                self.data.setByKey(i, 0, 'wintime')
            if ban > 0:
                self.data.addByKey(i, -1, 'ban')
            if wintime == 0 and ban == 0 and rating == 0:  # 删除三无用户
                self.data.deleteByKey(i)
        return

    def APIGET(self, baseurl, params):
        headers = {'Cookie': self.cookie}
        res = requests.get(baseurl, params=params, headers=headers)
        res.encoding = 'utf-8'
        return res.text

    def APIPOST(self, baseurl, data):
        headers = {'Cookie': self.cookie}
        res = requests.post(baseurl, data=data, headers=headers)
        res.encoding = 'utf-8'
        return res.text

    def GetUserInfoByUid(self, uid):
        res = json.loads(self.APIGET('https://kana.byha.top:444/api/user/info?', {'uid': str(uid)}))
        return res['msg']

    def GetUserLevelByUid(self, uid):
        res = json.loads(self.APIPOST('https://kana.byha.top:444/api/user/level', {'uid': str(uid)}))
        return res['msg']

    def GetUidByUsername(self, username):
        res = self.data.getByKey(username, 'uid')
        if res != 0:
            return res
        res = json.loads(self.APIGET('https://kana.byha.top:444/api/user/name2id?', {'uname': username}))
        if res['msg'] == 'No Such User':
            return 0
        self.data.setByKey(username, res['msg'], 'uid')
        return res['msg']

    def getUserInRoom(self):
        a = str(self.APIGET('https://kana.byha.top:444/checkmate/room', {}))
        ans = ''
        uname = []
        while True:
            g = re.search(r'<th>[\s\S]*?</th>', a)
            if g:
                tmp = g.group()
                if tmp.find(self.username) != -1 and tmp.find(r'/checkmate/room/') == -1:
                    ans = tmp[4:len(tmp) - 5]
                    break
                a = a[a.find(tmp) + 1:]
            else:
                break
        while True:
            pos = ans.find(';')
            if pos == -1 or len(uname) == 8:
                break
            uname.append(ans[:pos])
            ans = ans[pos + 1:]
        return uname

    def Main(self):
        self.driver = webdriver.Chrome()  # 浏览器
        # self.driver = webdriver.Firefox()
        self.Login()
        self.EnterRoom()
        self.On = True
        self.table = self.driver.find_element_by_tag_name("tbody")
        flag = False
        ban = 0
        try:
            self.data.readData()
        except:
            pass
        freetime = 0
        tmp = self.driver.get_cookies()
        for i in tmp:
            if i['name'] == 'client_session':
                self.cookie = 'client_session=' + i['value']
                break
        print(self.cookie)
        threading.Thread(target=self.CommandLine, name="command").start()
        while True:
            curTime = datetime.datetime.now()
            if curTime.hour not in range(8, 23):
                self.On = False
                self.updateData()
                self.data.saveData()
                self.Logout()
                self.driver.close()
                return
            if self.driver.current_url != self.url:
                self.EnterRoom()
                sleep(10)
                continue
            ac = ActionChains(self.driver)
            ac.send_keys(Keys.CONTROL).perform()  # 防踢
            try:
                if self.driver.find_element_by_id("game-status").get_attribute('innerHTML') != "游戏中":
                    if flag:
                        flag = False
                    sleep(0.2)
                    self.ispre = False
                else:
                    freetime = 0
                    self.botMove()
                    continue
                flag = True
            except:
                continue
            freetime += 1
            if freetime % 480 == 10 and not self.isSecret:
                self.sendMessage("【提示】" + random.choice(self.tips))
            try:
                tmp = self.driver.find_element_by_id("swal2-content").get_attribute('innerText')
                tmp = tmp[0:tmp.find("赢了")]
                if tmp != '':
                    ac = ActionChains(self.driver)
                    ac.send_keys(Keys.ENTER).perform()
                    if self.data.getByKey(tmp, 'ban') > 0 and self.mp.size in [9, 10]:
                        ban = time.time()
                        self.sendMessage('您已被封禁，剩余' + str(self.data.getByKey(tmp, 'ban')) + '天')
                    elif tmp != self.username and self.mp.size in [9, 10]:
                        self.data.addByKey(tmp, 1, 'wintime')
                        if self.data.getByKey(tmp, 'wintime') > 30:
                            self.data.setByKey(tmp, 7, 'ban')
                            self.data.setByKey(tmp, 0, 'Rating')
                            self.sendMessage('您已被封禁，剩余' + str(self.data.getByKey(tmp, 'ban')) + '天')
                            ban = time.time()
                        else:
                            self.sendMessage('您已单挑' + str(self.data.getByKey(tmp, 'wintime')) + '次')
                    if self.mp.size not in [9, 10]:
                        self.gameRatingCalc(tmp)
                    self.data.saveData()
            except:
                pass
            try:
                checkBox = self.driver.find_element_by_class_name("form-check-input")  # 防私密
                if (checkBox.is_selected() and not self.isSecret) or (not (checkBox.is_selected()) and self.isSecret):
                    checkBox.click()
                randomBtn = self.driver.find_element_by_css_selector('[data="' + self.selectedMap + '"]')
                randomBtn.click()
            except:
                pass
            try:
                if self.isAutoReady and self.driver.find_element_by_id("ready").get_attribute(
                        'innerHTML') == "准备" and time.time() - ban > 600:
                    ac = ActionChains(self.driver)
                    ac.click(self.driver.find_element_by_id("ready")).perform()
                if self.driver.find_element_by_id("ready").get_attribute(
                        'innerHTML') == "取消准备" and time.time() - ban <= 600:
                    ac = ActionChains(self.driver)
                    ac.click(self.driver.find_element_by_id("ready")).perform()
            except:
                pass
            try:
                self.userCount = int(self.driver.find_element_by_id("total-user").text)
            except:
                pass
        return


a = Bot()
while True:
    curTime = datetime.datetime.now()
    if curTime.hour in range(8, 23):
        a.Main()
    sleep(60)

import random
import re
import time
import copy
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
import json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.nlp.v20190408 import nlp_client, models


class Bot(object):
    """
    https://kana.byha.top:444/post/6735
    https://www.luogu.com.cn/paste/nbyi7ds9
    """

    def __init__(self, username, password, roomId, isSecret, controller, isAutoReady=True):
        self.kanaLink = "https://kana.byha.top:444/"
        self.driver = webdriver.Chrome()  # 浏览器
        # self.driver = webver.Firefox()
        self.username = username  # 用户名
        self.password = password  # 密码
        self.roomId = roomId  # 房间号
        self.isSecret = isSecret  # 是否为私密房间
        self.isAutoReady = isAutoReady  # 是否主动准备
        self.mpType = [[0 for i in range(25)] for j in range(25)]  # 属性地图
        self.mpTmp = [[0 for i in range(25)] for j in range(25)]  # 兵力地图
        self.mpBelong = [[0 for i in range(25)] for j in range(25)]  # 颜色地图
        self.di = [[-1, 0], [0, 1], [1, 0], [0, -1]]  # 方向
        self.q = []
        self.error = False
        self.vis = [[False for i in range(25)] for j in range(25)]  # 是否走过
        self.sx = self.sy = 0  # 家的位置
        self.homes = []  # 敌人的家
        self.size = 20
        self.tmpQ = []
        self.tmpVis = [[False for i in range(25)] for j in range(25)]
        self.route = []  # 进攻路线
        self.endTag = False
        self.ansLen = 100000
        self.freeTime = 0  # 空闲时间
        self.TIME_PER_TURN = 0.24  # 每回合的等待时间
        self.msg = []  # 消息区
        self.waittime = {}  # 等待时间
        self.commands = {'help (command)': ['查看命令列表（或命令command的用法）', 0], 'refresh': ['强制刷新', 20],
                         'info': ['获取Bot的工作信息', 100],
                         'chat [xxx]': ['与Bot对话', 5],
                         'query (i)': ['查询自己（或玩家i）的分数', 0],
                         'choose (mapname/mapid)': ['查看地图票数榜（或给mapname/mapid地图投票）', 5],
                         'send [uname] [x]': ['赠送x点分数给用户名为uname的玩家', 5],
                         'draw [n]' : ['抽奖n次', '10*n']}
        self.aToB = {'help': 'help (command)', 'refresh': 'refresh', 'info': 'info',
                     'chat': 'chat [xxx]', 'query': 'query (i)',
                     'choose': 'choose (mapname/mapid)', 'send': 'send [uname] [x]', 'draw' : 'draw [n]'}
        self.mapNameToMapID = {'随机': '1', '迷宫': '2', '空白': '3', '流浪': '5', '排位': '6', 'BRA': '7'}
        self.playerVote = {}
        self.mapVoted = {1: 0, 2: 0, 3: 0, 5: 0, 6: 0, 7: 0}
        self.tips = ['Bot的扩张优先级：主基地>城市>敌方领地>空白土地>我方领地',
                     'Bot在每回合有1/5的概率发起掏家', '若自身主基地受到威胁，Bot会优先防守', 'Bot在每回合有1/15的概率发起随机扩张', 'Bot更倾向于选取靠外的格子进行扩张'
            , 'Bot的随机扩张目标是周围7*7范围内有不少于5个敌方领地的格子',
                     '在n人局获胜可以获得(n-1)^2分', 'mapname与mapid的映射表：' + str(self.mapNameToMapID),
                     ]
        tmp = list(self.commands.keys())
        for x in tmp:
            self.tips.append('命令' + x + ': ' + self.commands[x][0] + '（花费' + str(self.commands[x][1]) + '点分数）')
        self.gameCnt = 0
        self.startTime = time.time()
        self.controller = controller
        self.gameStartTime = time.time()
        fo = open('secret')
        s = fo.readlines()
        self.SecretId = s[0].strip()
        self.SecretKey = s[1].strip()
        self.score = {}
        self.selectedMap = '1'
        self.defaultSelectedMap = '1'
        self.isAutoSave = False

    def SendKeyToTable(self, key):
        ac = ActionChains(self.driver)
        ac.send_keys(key).perform()

    def dist(self, xx1, yy1, xx2, yy2):
        return abs(xx1 - xx2) + abs(yy1 - yy2)

    def EnterRoom(self):
        """
        进入指定房间
        :return:
        """
        self.driver.get(
            "https://kana.byha.top:444/checkmate/room/" + self.roomId)
        if self.isSecret:
            settingBtn = self.driver.find_element_by_class_name(
                "form-check-input")
            ac = ActionChains(self.driver)
            ac.click(settingBtn).perform()
        print("Bot已就位！")

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
        self.size = int(cnt ** 0.5)
        if not (self.size == 9 or self.size == 10 or self.size == 19 or self.size == 20):
            return
        for i in range(self.size):
            for j in range(self.size):
                p = stype[0]
                stype.pop(0)
                if p.find(" city ") != -1 or p.find(" empty-city ") != -1:
                    self.mpType[i + 1][j + 1] = 5
                elif p.find(" crown ") != -1:
                    self.mpType[i + 1][j + 1] = 2
                elif p.find(" mountain ") != -1 or p.find(" obstacle ") != -1:
                    self.mpType[i + 1][j + 1] = 1
                elif p.find(" gas ") != -1:
                    self.mpType[i + 1][j + 1] = 1
                elif p.find(" null ") != -1 and p.find(" grey ") != -1:
                    self.mpType[i + 1][j + 1] = 0
                elif p.find(" null ") != -1 and p.find(" grey ") == -1:
                    self.mpType[i + 1][j + 1] = 3
                else:
                    self.mpType[i + 1][j + 1] = -1
                if p.find(" own ") != -1:
                    self.mpBelong[i + 1][j + 1] = 1
                else:
                    self.mpBelong[i + 1][j + 1] = 2
                if self.mpType[i + 1][j + 1] == 2 and self.mpBelong[i + 1][j + 1] == 1:
                    self.sx = i + 1
                    self.sy = j + 1
                p = stmp[0]
                stmp.pop(0)
                try:
                    self.mpTmp[i + 1][j + 1] = int(p)
                except:
                    self.mpTmp[i + 1][j + 1] = 0
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

    def UpdateScore(self, uname, cost):
        if uname == self.controller:
            return True
        try:
            if self.score[uname] < cost:
                return False
            else:
                self.score[uname] -= cost
                self.score[self.username] += cost
                return True
        except:
            return False

    def saveData(self, filename = 'data'):
        uname = list(self.score.keys())
        data = open(filename, mode='w')
        data.write(str(len(uname)) + '\n')
        for i in uname:
            data.write(i + '\n')
            data.write(str(self.score[i]) + '\n')
        data.flush()
        data.close()
        return

    def readData(self, filename = 'data'):
        self.score = {}
        data = open(filename, mode='r')
        s = data.readlines()
        n = int(s[0].strip())
        for i in range(n):
            uname = s[2 * i + 1].strip()
            score = int(s[2 * (i + 1)].strip())
            self.score[uname] = score
        data.close()
        return

    def CommandLine(self):  # 命令行
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
        if tmp[0] == 'refresh':
            if self.UpdateScore(cur[0], self.commands['refresh'][1]):
                if time.time() - self.gameStartTime < 300:
                    self.sendMessage("游戏开始后5分钟才能使用刷新")
                else:
                    self.EnterRoom()
                    print("refreshed by " + cur[0])
            else:
                self.sendMessage('分数不足')
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
                    self.sendMessage('命令' + x + ': ' + self.commands[x][0] + '（花费' + str(
                        self.commands[x][1]) + '点分数）')
                except:
                    self.sendMessage('未找到该命令')
            else:
                self.sendMessage('需要0或1个参数，发现' + str(tot) + '个')
        if tmp[0] == 'info':
            if self.UpdateScore(cur[0], self.commands['info'][1]):
                uname = list(self.score.keys())
                winners = '<strong>分数排行榜：</strong><br>'
                winnerList = []
                cmp = lambda s1: s1[1]
                for i in uname:
                    winnerList.append([i, self.score[i]])
                winnerList.sort(key=cmp, reverse=True)
                self.sendMessage(
                    '<br><strong>Bot工作状态：</strong><br>已运行' + str(
                        round(time.time() - self.startTime, 1)) + 's<br>' + '参战' + str(self.gameCnt) + '局<br>')
                self.sendMessage('当前奖池：' + str(self.score[self.username]) + '分')
                for i in winnerList:
                    winners += i[0] + ':' + str(i[1]) + '分<br>'
                    if len(winners) >= 70:
                        self.sendMessage('<br>' + winners)
                        winners = ''
                if winners != '':
                    self.sendMessage('<br>' + winners)
            else:
                self.sendMessage('分数不足')
        if tmp[0] == 'query':
            if tot != 0 and tot != 1:
                self.sendMessage('需要0或1个参数，发现' + str(tot) + '个')
            elif tot == 0:
                try:
                    self.sendMessage(str(self.score[cur[0]]) + '分')
                except:
                    self.sendMessage('0分')
            elif tot == 1:
                try:
                    self.sendMessage(str(self.score[tmp[1]]) + '分')
                except:
                    self.sendMessage('0分')
        if tmp[0] == 'chat':
            if self.UpdateScore(cur[0], self.commands['chat [xxx]'][1]):
                if tot != 1:
                    self.sendMessage('需要1个参数，发现' + str(tot) + '个')
                else:
                    try:
                        cred = credential.Credential(self.SecretId, self.SecretKey)
                        httpProfile = HttpProfile()
                        httpProfile.endpoint = "nlp.tencentcloudapi.com"
                        clientProfile = ClientProfile()
                        clientProfile.httpProfile = httpProfile
                        client = nlp_client.NlpClient(cred, "ap-guangzhou", clientProfile)

                        req = models.ChatBotRequest()
                        params = {
                            "Query": tmp[1]
                        }
                        req.from_json_string(json.dumps(params))

                        resp = client.ChatBot(req)
                        s = resp.Reply
                        self.sendMessage(s)

                    except TencentCloudSDKException as err:
                        print(err)
            else:
                self.sendMessage('分数不足')
        if tmp[0] == 'choose':
            if cur[0] == self.controller and tot == 2 and tmp[2] == '-f':
                self.defaultSelectedMap = tmp[1]
                self.sendMessage('selectedMap = ' + self.selectedMap + ' fixed')
            elif self.UpdateScore(cur[0], self.commands['choose (mapname/mapid)'][1]):
                if tot != 1 and tot != 0:
                    self.sendMessage('需要0或1个参数，发现' + str(tot) + '个')
                elif tot == 1:
                    if tmp[1].isdigit():
                        if 1 <= int(tmp[1]) <= 7 and int(tmp[1]) != 4:
                            try:
                                if self.playerVote[cur[0]] != 0:
                                    self.mapVoted[self.playerVote[cur[0]]] -= 1
                            except:
                                pass
                            self.playerVote[cur[0]] = int(tmp[1])
                            self.mapVoted[self.playerVote[cur[0]]] += 1
                            self.sendMessage('vote for ' + tmp[1])
                        else:
                            self.sendMessage('参数不在范围内')
                    else:
                        try:
                            try:
                                if self.playerVote[cur[0]] != 0:
                                    self.mapVoted[self.playerVote[cur[0]]] -= 1
                            except:
                                pass
                            self.playerVote[cur[0]] = int(self.mapNameToMapID[tmp[1]])
                            self.mapVoted[self.playerVote[cur[0]]] += 1
                            self.sendMessage('vote for ' + tmp[1])
                        except:
                            self.sendMessage('参数不在范围内')
                elif tot == 0:
                    self.sendMessage(str(self.mapVoted))
            else:
                self.sendMessage('分数不足')
        if tmp[0] == 'send':
            if self.UpdateScore(cur[0], self.commands['send [uname] [x]'][1]):
                if tot != 2:
                    self.sendMessage('需要2个参数，发现' + str(tot) + '个')
                else:
                    try:
                        x = int(tmp[2])
                        if x <= 0:
                            raise ValueError('')
                    except:
                        self.sendMessage('参数不在范围内')
                    else:
                        try:
                            if x > self.score[cur[0]]:
                                self.sendMessage('分数不足')
                            else:
                                self.score[cur[0]] -= x
                                try:
                                    self.score[tmp[1]] += x
                                except:
                                    self.score[tmp[1]] = x
                                self.sendMessage('成功')
                        except:
                            self.sendMessage('分数不足')
            else:
                self.sendMessage('分数不足')
        if tmp[0] == 'draw':
            if tot != 1:
                self.sendMessage('需要1个参数，发现' + str(tot) + '个')
            else:
                try:
                    cnt = int(tmp[1])
                except:
                    self.sendMessage('参数应为整数')
                else:
                    if cnt <= 0:
                        self.sendMessage('参数不在范围内')
                    elif self.UpdateScore(cur[0], 10 * cnt):
                        res = 0
                        role = [[3, 0.2], [10, 0.1], [87, 0]]
                        for i in range(cnt):
                            curtry = random.randint(1, 100)
                            rate = 0
                            for j in role:
                                rate += j[0]
                                if curtry <= rate:
                                    pos = int(self.score[self.username] * j[1])
                                    res += pos
                                    self.score[self.username] -= pos
                                    break
                        try:
                            self.score[cur[0]] += res
                        except:
                            self.score[cur[0]] = res
                        self.sendMessage('恭喜获得' + str(res) + '分')
                    else:
                        self.sendMessage('分数不足')
        if tmp[0] == 'kill':
            if cur[0] == self.controller:
                self.Kill()
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
                self.saveData()
                self.sendMessage('saved')
            else:
                self.sendMessage('权限不足')
        if tmp[0] == 'readdata':
            if cur[0] == self.controller:
                try:
                    if tot == 1:
                        self.readData(tmp[1])
                    else:
                        self.readData()
                    self.sendMessage('read')
                except:
                    self.sendMessage('error')
            else:
                self.sendMessage('权限不足')
        if tmp[0] == 'setautosave':
            if cur[0] == self.controller:
                self.isAutoSave = not self.isAutoSave
                self.sendMessage('autosave = ' + str(self.isAutoSave))
            else:
                self.sendMessage('权限不足')
        if tmp[0] == 'setscore':
            if cur[0] == self.controller:
                self.score[tmp[1]] = int(tmp[2])
                self.sendMessage('score = ' + tmp[2])
            else:
                self.sendMessage('权限不足')
        return

    def SelectLand(self, x, y):  # 选择土地
        try:
            self.driver.find_element_by_id(
                "td-" + str((x - 1) * self.size + y)).click()
            return
        except:
            return

    def sendMessage(self, msg):  # 发送消息
        if len(msg) >= 92:
            self.sendMessage(msg[0:90])
            self.sendMessage(msg[90:len(msg)])
        messageBox = self.driver.find_element_by_id("msg-sender")
        ac = ActionChains(self.driver)
        ac.send_keys_to_element(messageBox, msg)
        ac.send_keys(Keys.ENTER).perform()
        return

    def Login(self):
        """
            登录，如果出现异常则在5S后退出
            :return:
        """
        print("正在登录…")
        self.driver.get(self.kanaLink)
        usernameBox = self.driver.find_element_by_name("username")
        passwordBox = self.driver.find_element_by_name("pwd")
        ac = ActionChains(self.driver)

        # 输入账号密码并登录
        ac.send_keys_to_element(usernameBox, self.username)
        ac.send_keys_to_element(passwordBox, self.password)
        sleep(10)  # 等待用户手动输入验证码
        ac.click(self.driver.find_element_by_id("submitButton")).perform()
        try:
            WebDriverWait(self.driver, 8).until(EC.url_to_be(self.kanaLink))
            print("登录成功！")
        except TimeoutException:
            print("网络连接出现问题或账密错误！\n程序将在5秒后退出")
            sleep(5)
            self.driver.close()
            del self

    def Ready(self):
        try:
            ac = ActionChains(self.driver)
            ac.click(self.driver.find_element_by_id("ready")).perform()
        except:
            return

    def Kill(self):
        self.driver.close()
        del self

    def Pr(self, c):
        self.SendKeyToTable(c)
        if c != "F":
            self.freeTime = 0
        return

    def IsOutside(self, x, y):
        for i in range(4):
            px = x + self.di[i][0]
            py = y + self.di[i][1]
            if px >= 1 and px <= self.size and py >= 1 and py <= self.size and self.mpBelong[px][py] == 2:
                return True
        return False

    def ChangeTarget(self):
        insideAnsTmp = self.mpTmp[self.sx][self.sy]
        insideAnsX = self.sx
        insideAnsY = self.sy
        outsideAnsTmp = 0
        outsideAnsX = 0
        outsideAnsY = 0
        for p in range(self.size):
            for q in range(self.size):
                i = p + 1
                j = q + 1
                if self.mpBelong[i][j] == 1:
                    if self.IsOutside(i, j):
                        if self.mpTmp[i][j] > outsideAnsTmp:
                            outsideAnsTmp = self.mpTmp[i][j]
                            outsideAnsX = i
                            outsideAnsY = j
                    else:
                        if self.mpTmp[i][j] > insideAnsTmp:
                            insideAnsTmp = self.mpTmp[i][j]
                            insideAnsX = i
                            insideAnsY = j
        if outsideAnsTmp * 5 >= insideAnsTmp:
            self.sx = outsideAnsX
            self.sy = outsideAnsY
        else:
            self.sx = insideAnsX
            self.sy = insideAnsY
        self.q.append([self.sx, self.sy])
        if random.randint(0, 1) == 1:
            self.vis = [[False for i in range(25)] for j in range(25)]
        self.vis[self.sx][self.sy] = True
        self.SelectLand(self.sx, self.sy)
        return

    def dfsRoute(self, x, y, ex, ey, cnt):
        if x == ex and y == ey and cnt < self.ansLen:
            self.ansLen = cnt
            self.route = copy.deepcopy(self.tmpQ)
            # print("finished")
            # print(self.tmpQ)
            # print(cnt)
            return
        if cnt >= self.ansLen:
            return
        tmpI = [0, 1, 2, 3]
        random.shuffle(tmpI)
        ansI = 0
        ansDis = 10000
        for i in tmpI:
            if self.endTag:
                return
            px = x + self.di[i][0]
            py = y + self.di[i][1]
            if 1 <= px <= self.size and 1 <= py <= self.size and (not self.tmpVis[px][py]) and \
                    self.mpType[px][py] != 1:
                if abs(px - ex) + abs(py - ey) < ansDis:
                    ansDis = abs(px - ex) + abs(py - ey)
                    ansI = i
        px = x + self.di[ansI][0]
        py = y + self.di[ansI][1]
        if 1 <= px <= self.size and 1 <= py <= self.size and (not self.tmpVis[px][py]) and \
                self.mpType[px][py] != 1:
            self.tmpVis[px][py] = True
            self.tmpQ.append([ansI, x, y])
            # print(i, x, y)
            self.dfsRoute(px, py, ex, ey, cnt + 1)
            self.tmpQ.remove([ansI, x, y])
            if random.randint(0, 10) >= 2:
                self.tmpVis[px][py] = False
        return

    def Attack(self, x, y, ex, ey):
        self.tmpQ = copy.deepcopy([])
        self.route = []
        self.endTag = False
        self.tmpVis = [[False for i in range(25)] for j in range(25)]
        self.tmpVis[x][y] = True
        self.ansLen = 10000
        self.dfsRoute(x, y, ex, ey, 0)
        if len(self.route) < 1:
            return
        for p in self.route:
            i = p[0]
            self.GetMap()
            if x < 1 or y < 1 or x > self.size or y > self.size or self.mpBelong[x][y] == 2 or self.mpTmp[x][y] < 2:
                return
            if i == 0:
                self.Pr('W')
                x -= 1
            elif i == 1:
                self.Pr('D')
                y += 1
            elif i == 2:
                self.Pr('S')
                x += 1
            else:
                self.Pr('A')
                y -= 1
            sleep(self.TIME_PER_TURN)
        return

    def checkHome(self):
        for i in range(self.sx - 1, self.sx + 1):
            for j in range(self.sy - 1, self.sy + 1):
                if 0 < i <= self.size and 0 < j <= self.size and self.mpBelong[i][j] == 2 and \
                        self.mpType[i][j] == 3:
                    return True
        return False

    def Hunt(self, x, y):
        for i in range(1, self.size):
            for j in range(1, self.size):
                tmp = 0
                flag = False
                if self.mpType[i][j] != 0 and self.mpTmp[i][j] != 3:
                    continue
                for k in range(i - 3, i + 3):
                    for w in range(j - 3, j + 3):
                        if 1 <= k <= self.size and 1 <= w <= self.size and self.mpBelong[k][w] == 2 and self.mpType[k][
                            w] != 1:
                            tmp += 1
                        else:
                            flag = True
                            break
                    if flag:
                        break
                if tmp >= 5:
                    self.Attack(x, y, i, j)
                    return
        return

    def botMove(self):
        sleep(self.TIME_PER_TURN)
        self.CommandLine()
        self.playerVote = {}
        self.mapVoted = {1: 0, 2: 0, 3: 0, 5: 0, 6: 0, 7: 0}
        self.mapVoted[int(self.defaultSelectedMap)] = 1
        x = 0
        y = 0
        tryTime = 0
        try:
            if self.driver.find_element_by_id("game-status").get_attribute('innerHTML') != "游戏中":
                return
        except:
            self.EnterRoom()
            sleep(self.TIME_PER_TURN * 5)
        self.GetMap()
        while True:
            if len(self.q) == 0:
                self.ChangeTarget()
            x = self.q[0][0]
            y = self.q[0][1]
            tryTime += 1
            self.q.pop(0)
            if not (self.mpTmp[x][y] <= 1 and self.mpType[x][y] != 2 and tryTime <= 10):
                break
        if tryTime > 10:
            return
        if self.mpTmp[x][y] <= 1:
            return
        if self.mpBelong[x][y] == 2:
            return
        if self.mpType[x][y] == 2 and self.mpBelong[x][y] == 1:
            self.Pr('Z')
        for i in range(self.size):
            for j in range(self.size):
                if self.mpType[i + 1][j + 1] == 2 and self.mpBelong[i + 1][j + 1] == 2 and (
                        not ([i + 1, j + 1] in self.homes)):
                    self.homes.append([i + 1, j + 1])
        if [x, y] in self.homes:
            self.homes.remove([x, y])
        if len(self.homes) > 0 and random.randint(1, 5) == 1 and self.mpTmp[x][y] > 30:
            g = random.randint(0, len(self.homes) - 1)
            self.Attack(x, y, self.homes[g][0], self.homes[g][1])
            return
        if self.mpTmp[x][y] > 20 and self.dist(x, y, self.sx, self.sy) >= 4 and self.checkHome():
            self.Attack(x, y, self.sx, self.sy)
            return
        if self.mpTmp[x][y] > 200 and random.randint(1, 15) == 1:
            self.Hunt(x, y)
            return
        ansTmp = 0
        ansI = -1
        tmpI = [0, 1, 2, 3]
        random.shuffle(tmpI)
        for i in tmpI:
            px = x + self.di[i][0]
            py = y + self.di[i][1]
            if self.size >= px >= 1 != self.mpType[px][py] and 1 <= py <= self.size and (
                    not self.vis[px][py]) and (self.mpType[px][py] != 5 or self.mpTmp[x][y] > self.mpTmp[px][py]):
                currentTmp = 0
                if self.mpBelong[px][py] == 2:
                    if self.mpType[px][py] == 2:
                        currentTmp = 10
                    elif self.mpType[px][py] == 5:
                        currentTmp = 8
                    elif self.mpType[px][py] == 3:
                        currentTmp = 5
                    else:
                        currentTmp = 3
                else:
                    currentTmp = 1
                if currentTmp > ansTmp:
                    ansTmp = currentTmp
                    ansI = i
        if ansI == -1:
            return
        px = x + self.di[ansI][0]
        py = y + self.di[ansI][1]
        self.vis[px][py] = True
        self.q.append([px, py])
        if ansI == 0:
            self.Pr('W')
        elif ansI == 1:
            self.Pr('D')
        elif ansI == 2:
            self.Pr('S')
        else:
            self.Pr('A')
        self.botMove()
        return

    def Main(self):
        self.Login()
        self.EnterRoom()
        self.freeTime = 0
        self.table = self.driver.find_element_by_tag_name("tbody")
        flag = False
        lastSaveTime = 0
        while True:
            if self.driver.current_url == "https://kana.byha.top:444":
                self.EnterRoom()
                sleep(self.TIME_PER_TURN * 5)
                continue
            try:
                tmp = self.driver.find_element_by_id("swal2-content").get_attribute('innerText')
                tmp = tmp[0:tmp.find("赢了")]
                if tmp != '':
                    try:
                        self.userCount = int(
                            self.driver.find_element_by_id("total-user").text)
                    except:
                        self.userCount = 2
                    addtmp = (self.userCount - 1) ** 2
                    if tmp in self.score:
                        self.score[tmp] += addtmp
                    else:
                        self.score[tmp] = addtmp
                    ac = ActionChains(self.driver)
                    ac.send_keys(Keys.ENTER).perform()
            except:
                pass
            # try:
            #     self.driver.find_element_by_class_name('swal2-confirm swal2-styled').click()
            # except:
            #     pass
            try:
                if self.isAutoReady and self.driver.find_element_by_id("ready").get_attribute('innerHTML') == "准备":
                    self.Ready()
                speed = int(
                    self.driver.find_element_by_id("settings-gamespeed-input-display").get_attribute('innerText'))
                self.TIME_PER_TURN = 0.24 * 4.0 / speed
            except:
                pass
            if self.isAutoSave and self.freeTime == 1:
                self.saveData()
                if time.time() - lastSaveTime >= 1800:
                    lastSaveTime = time.time()
                    self.saveData('data' + str(time.time()))
            self.CommandLine()
            self.Pr('F')  # 防踢
            self.GetMap()
            self.freeTime += 1
            # print(self.freeTime)
            sleep(0.2)
            if self.freeTime % 480 == 10 and not self.isSecret:
                self.sendMessage("【提示】" + self.tips[random.randint(0, len(self.tips) - 1)])
                # self.sendMessage(
                #   '欢迎来<a href="' + "https://kana.byha.top:444/checkmate/room/" + self.roomId + '">' + self.roomId + '</a>玩')
            try:
                checkBox = self.driver.find_element_by_class_name("form-check-input")  # 防私密
                if (checkBox.is_selected() and not self.isSecret) or (not (checkBox.is_selected()) and self.isSecret):
                    checkBox.click()
                current = list(self.mapVoted.keys())
                currentList = []
                cmp = lambda s1: s1[1]
                for i in current:
                    currentList.append([i, self.mapVoted[i]])
                currentList.sort(key=cmp, reverse=True)
                self.selectedMap = str(currentList[0][0])
                randomBtn = self.driver.find_element_by_css_selector('[data="' + self.selectedMap + '"]')
                randomBtn.click()
            except:
                pass
            try:
                if self.driver.find_element_by_id("game-status").get_attribute('innerHTML') != "游戏中":
                    self.gameStartTime = time.time()
                    if flag:
                        self.gameCnt += 1
                        flag = False
                    continue
                flag = True
            except:
                continue
            self.sx = 0
            self.sy = 0
            for i in range(self.size):
                for j in range(self.size):
                    if self.mpBelong[i + 1][j + 1] == 1 and self.mpType[i + 1][j + 1] == 2:
                        self.sx = i + 1
                        self.sy = j + 1
            if self.sx == 0 or self.sy == 0:
                continue
            self.ChangeTarget()
            self.botMove()
        return


print("输入用户名：")
t1 = input()
print("输入密码：")
t2 = input()
print("输入房间号：")
t3 = input()
print("是否私密？(Y/N)")
t4 = input()
print("输入控制者：")
t5 = input()
a = Bot(t1, t2, t3, t4 == "Y", t5)
a.Main()

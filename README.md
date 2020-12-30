# CheckmateBot
CheckmateBot

框架：<https://github.com/Polythefake/KanaBot>

**特别提示：验证码需要用户手动输入**

### 关于控制者

为了方便远程控制，特推出控制者功能，被标记为控制者的用户可以执行高级命令，且不受命令冷却时间限制。

### 命令说明

在每个命令中，```[x]``` 表示 ```x``` 是必选参数，```(x)``` 表示 ```x``` 是可选参数。

| 命令 |含义  |特殊说明|冷却时间|是否为高级命令|
| :----------: | :----------: | :----------: | :----------: | :----------: |
|```help```  |获取命令帮助  |/ |/|否|
|```refresh```  |强制刷新  |游戏开始后5min可用 |60s|否|
|```info```  |获取工作信息  |/ |60s|否|
|```attack [x] [y]```  |攻击第x行第y列的格子  |仅限游戏中可用 |60s|否|
|```chat [xxx]```  |与Bot对话  |/ |5s|否|
|```kill```  |关闭Bot  |/ |/|**是**|
|```enter [roomid]```  |进入roomid房间  |/ |/|**是**|
|```setsecret```  |切换房间私密状态  |/ |/|**是**|

对于同一个用户，命令冷却时间为 1min

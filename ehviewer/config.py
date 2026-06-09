# EhViewer漫画管理工具 - 配置常量

SPIDER_INFO_FILENAME = ".ehviewer"
EHVIEWER_PACKAGE = "com.xjs.ehviewer"
DEFAULT_THRESHOLD = 0.9

# 手机上的路径
EXPORT_DB_DIR = "/storage/emulated/0/EhViewer/data"
DOWNLOAD_DIR = "/storage/emulated/0/EhViewer/download"

# 本工具推送回手机的已清理数据库文件名前缀。
# 拉取"最新导出"时据此跳过工具自己推送的文件, 避免基于旧快照反复操作。
PUSHED_DB_PREFIX = "ehviewer_cleaned_"

# 下载状态映射
STATE_NAMES = {0: "无", 1: "等待", 2: "下载中", 3: "完成", 4: "失败"}

"""
upsaclebus 日志和 Textual 配置模块
"""
from textual_logger import TextualLoggerManager

# Textual 布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体统计",
        "style": "lightyellow"
    },
    "current_progress": {
        "ratio": 4,
        "title": "🔄 文件处理",
        "style": "lightcyan"
    },
    "process_log": {
        "ratio": 1,
        "title": "📝 处理日志",
        "style": "lightmagenta"
    },
    "update_log": {
        "ratio": 1,
        "title": "ℹ️ 状态更新",
        "style": "lightblue"
    }
}


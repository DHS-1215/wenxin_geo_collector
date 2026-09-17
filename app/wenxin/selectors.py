"""文心助手页面选择器。"""

# ============================================================
# 输入区域
# ============================================================

TEXTAREA_SELECTOR = "#chat-textarea"

SEND_BUTTON_SELECTOR = ".ci-submit-button"

MODE_SELECTOR = '[data-testid="chat-mode-selector"]'

NEW_CHAT_SELECTOR = '[data-testid="aside-new-dialog-box"]'

# ============================================================
# 回答
# ============================================================

ANSWER_SELECTOR = ".cs-answer-container"

GENERATING_ANSWER_SELECTOR = (
    '.cs-answer-container[data-status="GENERATING"]'
)

COMPLETE_ANSWER_SELECTOR = (
    '.cs-answer-container[data-status="COMPLETE"]'
)

# ============================================================
# 回答正文
# ============================================================

MARKDOWN_SELECTOR = ".ai-entry-block.ai-markdown"

MARKDOWN_CONTENT_SELECTOR = (
    ".ai-entry-block.ai-markdown .marklang"
)

# ============================================================
# 引用 / 信源
# ============================================================

SOURCE_SELECTOR = (
    "li[data-long-press-ext-info]"
)

CITATION_SELECTOR = (
    '[aria-label*="参考文档"], '
    ".cosd-citation"
)

# ============================================================
# 页面主体
# ============================================================

CONVERSATION_FLOW_SELECTOR = (
    "#conversation-flow-container"
)

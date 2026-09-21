from __future__ import annotations


class WenxinControlFlowError(RuntimeError):
    """需要改变批次执行流程的文心异常。"""

    def __init__(
        self,
        message: str,
        *,
        task_id: str = "",
    ) -> None:
        super().__init__(message)
        self.task_id = task_id

    def bind_task(
        self,
        task_id: str,
    ) -> "WenxinControlFlowError":
        self.task_id = task_id
        return self


class WenxinQuotaExhaustedError(
    WenxinControlFlowError
):
    """当前账号对话/使用额度耗尽。"""


class WenxinRiskControlError(
    WenxinControlFlowError
):
    """疑似操作频繁、访问限制或安全验证。"""


class WenxinLoginRequiredError(
    WenxinControlFlowError
):
    """当前登录态失效，需要人工重新登录。"""
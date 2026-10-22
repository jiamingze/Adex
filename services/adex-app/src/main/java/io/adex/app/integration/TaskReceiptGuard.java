package io.adex.app.integration;

/** A final task mutation claim needs an application receipt, never a model assurance. */
public final class TaskReceiptGuard {
  private TaskReceiptGuard() {}

  public static String finalContent(String content, boolean receipt) {
    boolean task = content.matches("(?s).*(任务|待办|定时|提醒|自动安排).*");
    boolean claim =
        content.matches(
            "(?s).*(已(?:经)?(?:为你|帮你|替你|为您|帮您)?(?:创建|设置|安排|添加|修改|更新|暂停|取消|删除)|(?:创建|设置|修改|更新)成功).*");
    if (!receipt && task && claim) return "本轮尚未取得任务操作的执行回执，不能确认已经创建或修改。请明确需要操作的事项及时间，我会根据实际保存结果回复。";
    return content;
  }
}

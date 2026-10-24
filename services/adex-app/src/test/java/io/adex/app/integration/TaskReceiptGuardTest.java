package io.adex.app.integration;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class TaskReceiptGuardTest {
  @Test
  void modelProseCannotBecomeMutationReceipt() {
    assertTrue(TaskReceiptGuard.finalContent("已为你创建定时任务", false).contains("尚未取得"));
    assertEquals("已为你创建定时任务", TaskReceiptGuard.finalContent("已为你创建定时任务", true));
    assertEquals("建议每天整理新闻", TaskReceiptGuard.finalContent("建议每天整理新闻", false));
    assertFalse(TaskReceiptGuard.finalContent("已为你创建交易任务", false).contains("事项及时间"));
  }
}

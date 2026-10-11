package io.adex.automation;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication(scanBasePackages = "io.adex")
@EnableScheduling
public class AutomationMain {
  public static void main(String[] args) {
    SpringApplication.run(AutomationMain.class, args);
  }
}

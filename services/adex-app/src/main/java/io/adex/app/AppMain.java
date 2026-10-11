package io.adex.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication(scanBasePackages = "io.adex")
@EnableScheduling
public class AppMain {
  public static void main(String[] args) {
    SpringApplication.run(AppMain.class, args);
  }
}

package io.adex.app;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.mail.javamail.JavaMailSenderImpl;
import org.springframework.mail.javamail.MimeMessageHelper;
@Component
public class EmailNotifier {
 final Kernel k;
 public EmailNotifier(Kernel k){this.k=k;}
 @Scheduled(fixedDelay=10000)public void send(){
  if(Kernel.env("ADEX_SMTP_HOST","").isBlank())return;
  try{
   k.db.update("UPDATE email_deliveries SET status='UNKNOWN',error_code='DISPATCH_INTERRUPTED' WHERE status='IN_FLIGHT' AND dispatched_at<now()-interval '5 minutes'");
   k.db.update("INSERT INTO email_deliveries(notification_id,owner_id,recipient) SELECT n.id,n.owner_id,u.settings->>'email' FROM notifications n JOIN users u ON u.id=n.owner_id WHERE u.settings->>'email_notifications'='true' AND u.settings->>'email' IS NOT NULL AND n.created_at>now()-interval '1 day' ON CONFLICT DO NOTHING");
   var item=k.tx.execute(tx->{var rows=k.db.queryForList("SELECT e.*,n.title,n.body FROM email_deliveries e JOIN notifications n ON n.id=e.notification_id WHERE e.status='PREPARED' AND (SELECT count(*) FROM email_deliveries d WHERE d.owner_id=e.owner_id AND d.dispatched_at>now()-interval '1 day')<20 ORDER BY e.created_at FOR UPDATE OF e SKIP LOCKED LIMIT 1");if(rows.isEmpty())return null;var e=rows.getFirst();k.db.update("UPDATE email_deliveries SET status='IN_FLIGHT',dispatched_at=now() WHERE notification_id=?",e.get("notification_id"));return e;});
   if(item==null)return;
   try{var sender=new JavaMailSenderImpl();sender.setHost(Kernel.env("ADEX_SMTP_HOST"));sender.setPort(Integer.parseInt(Kernel.env("ADEX_SMTP_PORT","587")));sender.setUsername(Kernel.env("ADEX_SMTP_USERNAME",""));sender.setPassword(Kernel.env("ADEX_SMTP_PASSWORD",""));
    var p=sender.getJavaMailProperties();p.setProperty("mail.smtp.auth","true");p.setProperty("mail.smtp.starttls.enable","true");p.setProperty("mail.smtp.starttls.required","true");p.setProperty("mail.smtp.connectiontimeout","10000");p.setProperty("mail.smtp.timeout","10000");p.setProperty("mail.smtp.writetimeout","10000");
    var message=sender.createMimeMessage();var helper=new MimeMessageHelper(message,false,"UTF-8");helper.setTo(String.valueOf(item.get("recipient")));helper.setFrom(Kernel.env("ADEX_SMTP_FROM"));helper.setSubject(String.valueOf(item.get("title")));helper.setText(String.valueOf(item.get("body")),false);message.setHeader("X-Adex-Notification",String.valueOf(item.get("notification_id")));sender.send(message);
    k.db.update("UPDATE email_deliveries SET status='SUCCEEDED',completed_at=now() WHERE notification_id=? AND status='IN_FLIGHT'",item.get("notification_id"));
   }catch(Exception e){k.db.update("UPDATE email_deliveries SET status='UNKNOWN',error_code='SMTP_RESULT_UNKNOWN' WHERE notification_id=? AND status='IN_FLIGHT'",item.get("notification_id"));}
  }catch(Exception ignored){}
 }
}

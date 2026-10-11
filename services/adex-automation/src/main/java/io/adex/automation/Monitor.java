package io.adex.automation;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.bind.annotation.*;

@RestController
public class Monitor {
 final Kernel k;
 public Monitor(Kernel k){this.k=k;}
 UUID owner(HttpServletRequest r,String scope,Object resource){return Kernel.uuid(k.require(r,"app",scope,resource).get("owner"));}
 @GetMapping("/internal/monitors") public Object list(HttpServletRequest r){return Kernel.items(k.db.queryForList("SELECT m.*,s.query FROM monitor_subscriptions m JOIN monitor_sources s ON s.id=m.source_id WHERE owner_id=? ORDER BY created_at DESC",owner(r,"monitor:read",null)));}
 @PostMapping("/internal/monitors") public Object create(HttpServletRequest r,@RequestBody Map<String,Object> b){
  UUID owner=owner(r,"monitor:write",null);String query=Kernel.text(b,"query",300),keyword=Kernel.text(b,"keyword",100);
  String kind=String.valueOf(b.getOrDefault("kind","SEARCH"));if(!Set.of("SEARCH","WEATHER").contains(kind))throw Kernel.error(400,"INVALID_MONITOR_KIND");
  Map<String,Object> request=new TreeMap<>(),rule=new TreeMap<>();
  if(kind.equals("WEATHER")){
   for(String coordinate:List.of("latitude","longitude")){Object value=b.get(coordinate);if(!(value instanceof Number n)||!Double.isFinite(n.doubleValue())||Math.abs(n.doubleValue())>(coordinate.equals("latitude")?90:180))throw Kernel.error(400,"INVALID_COORDINATE");request.put(coordinate,value);}
   String metric=Kernel.text(b,"metric",50),operator=Kernel.text(b,"operator",4);if(!Set.of("temperature_2m","precipitation","wind_speed_10m").contains(metric)||!Set.of("gte","lte").contains(operator)||!(b.get("threshold") instanceof Number n)||!Double.isFinite(n.doubleValue()))throw Kernel.error(400,"INVALID_WEATHER_RULE");rule.put("metric",metric);rule.put("operator",operator);rule.put("threshold",n);
  }
  String sourceKey=kind.equals("SEARCH")?Kernel.memoryHash(query):Kernel.hash(k.encode(request));
  return k.tx.execute(s->{UUID source=Kernel.id();
   k.db.update("INSERT INTO monitor_sources(id,source_key,query,interval_seconds,kind,request) VALUES(?,?,?,900,?,?::jsonb) ON CONFLICT(source_key) DO NOTHING",source,sourceKey,query,kind,k.encode(request));
   source=k.db.queryForObject("SELECT id FROM monitor_sources WHERE source_key=?",UUID.class,sourceKey);
   if(k.db.queryForObject("SELECT count(*) FROM monitor_subscriptions WHERE owner_id=? AND active",Integer.class,owner)>=20)throw Kernel.error(429,"MONITOR_LIMIT");
   return k.row("INSERT INTO monitor_subscriptions(id,owner_id,origin_conversation_id,source_id,keyword,rule) VALUES(?,?,?,?,?,?::jsonb) RETURNING *",Kernel.id(),owner,Kernel.uuid(b.get("origin_conversation_id")),source,keyword,k.encode(rule));
  });
 }
 @DeleteMapping("/internal/monitors/{id}") public Object cancel(HttpServletRequest r,@PathVariable UUID id){if(k.db.update("UPDATE monitor_subscriptions SET active=false WHERE id=? AND owner_id=?",id,owner(r,"monitor:write",id))==0)throw Kernel.error(404,"MONITOR_NOT_FOUND");return Map.of("ok",true);}
 @Scheduled(fixedDelay=10000) public void poll(){
  try{
   var source=k.tx.execute(s->{var rows=k.db.queryForList("SELECT s.* FROM monitor_sources s WHERE next_poll_at<=clock_timestamp() AND (lease_until IS NULL OR lease_until<clock_timestamp()) AND EXISTS(SELECT 1 FROM monitor_subscriptions m WHERE m.source_id=s.id AND m.active) ORDER BY next_poll_at FOR UPDATE SKIP LOCKED LIMIT 1");if(rows.isEmpty())return null;
    return k.row("UPDATE monitor_sources SET epoch=epoch+1,lease_until=clock_timestamp()+interval '45 seconds' WHERE id=? RETURNING *",rows.getFirst().get("id"));});
   if(source==null)return;
   try{var data=k.call("tools","monitor:read",null,source.get("id"),"POST",source.get("kind").equals("WEATHER")?"/internal/monitor/weather":"/internal/monitor/search",source.get("kind").equals("WEATHER")?k.decode(String.valueOf(source.get("request"))):Map.of("query",source.get("query")));
    String text=k.encode(data.get("items"));String hash=Kernel.hash(text);
    k.tx.executeWithoutResult(tx->{if(k.db.update("UPDATE monitor_sources SET next_poll_at=clock_timestamp()+make_interval(secs=>interval_seconds),lease_until=NULL,last_error=NULL WHERE id=? AND epoch=? AND lease_until>clock_timestamp()",source.get("id"),source.get("epoch"))!=1)throw Kernel.error(409,"STALE_EXECUTION");
     UUID observation=Kernel.id();if(k.db.update("INSERT INTO observations(id,source_id,content_hash,payload) VALUES(?,?,?,?::jsonb) ON CONFLICT DO NOTHING",observation,source.get("id"),hash,k.encode(data))==0)return;
     var subscribers=k.db.queryForList("SELECT * FROM monitor_subscriptions WHERE source_id=? AND active AND (last_notified_at IS NULL OR last_notified_at<clock_timestamp()-make_interval(secs=>quiet_seconds)) FOR UPDATE",source.get("id"));
     for(var sub:subscribers){if(source.get("kind").equals("WEATHER")){
       var ruleData=k.decode(String.valueOf(sub.get("rule")));var item=(Map<?,?>)((List<?>)data.get("items")).getFirst();double value=((Number)item.get(String.valueOf(ruleData.get("metric")))).doubleValue(),threshold=((Number)ruleData.get("threshold")).doubleValue();if(ruleData.get("operator").equals("gte")?value<threshold:value>threshold)continue;
      }else if(!text.toLowerCase(Locale.ROOT).contains(String.valueOf(sub.get("keyword")).toLowerCase(Locale.ROOT)))continue;
      UUID event=Kernel.id();var payload=Map.of("event_id",event,"owner_id",sub.get("owner_id"),"origin_conversation_id",sub.get("origin_conversation_id"),"content","监控关键词「"+sub.get("keyword")+"」出现新信息：\n"+text,"source_id",source.get("id"));
      k.db.update("INSERT INTO monitor_intents(id,observation_id,subscription_id,payload) VALUES(?,?,?,?::jsonb) ON CONFLICT DO NOTHING",event,observation,sub.get("id"),k.encode(payload));k.db.update("UPDATE monitor_subscriptions SET last_notified_at=clock_timestamp() WHERE id=?",sub.get("id"));
     }
    });
   }catch(Exception error){k.db.update("UPDATE monitor_sources SET lease_until=NULL,next_poll_at=clock_timestamp()+interval '5 minutes',last_error='SOURCE_UNAVAILABLE' WHERE id=? AND epoch=?",source.get("id"),source.get("epoch"));}
  }catch(Exception ignored){}
 }
 @Scheduled(fixedDelay=3000)public void publish(){try{
  var row=k.tx.execute(s->{var rows=k.db.queryForList("SELECT * FROM monitor_intents WHERE delivered_at IS NULL AND (lease_until IS NULL OR lease_until<clock_timestamp()) ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1");if(rows.isEmpty())return null;return k.row("UPDATE monitor_intents SET claim_id=?,lease_until=clock_timestamp()+interval '30 seconds' WHERE id=? RETURNING *",Kernel.id(),rows.getFirst().get("id"));});if(row==null)return;
  var b=k.decode(String.valueOf(row.get("payload")));k.call("app","monitor:attach",b.get("owner_id"),b.get("origin_conversation_id"),"POST","/internal/monitors/attach",b);
  k.db.update("UPDATE monitor_intents SET delivered_at=now(),lease_until=NULL WHERE id=? AND claim_id=?",row.get("id"),row.get("claim_id"));
 }catch(Exception ignored){}}
}

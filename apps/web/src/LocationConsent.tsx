import { MapPin } from "lucide-react";
import { saveLocationPreference, type LocationMode } from "./locationContext";

/** In-chat consent; only the OS/browser presents the mandatory permission sheet. */
export function LocationConsent({ onChoose }: { onChoose: (mode: LocationMode) => void }) {
  function choose(mode: LocationMode) {
    saveLocationPreference(mode);
    onChoose(mode);
  }
  return (
    <article className="message assistant">
      <div className="message-avatar"><MapPin size={16} /></div>
      <section className="message-content location-consent" aria-labelledby="location-title">
        <strong id="location-title">使用你的位置查询</strong>
        <p>授权后，我会根据当前位置查询天气或附近地点。仅在相关查询时使用近似位置，不会后台追踪或自动记入长期记忆。</p>
        <div className="location-consent-actions">
          <button type="button" className="button primary" onClick={() => choose("device")}>
            <MapPin size={16} />使用当前位置
          </button>
          <button type="button" className="text-button" onClick={() => choose("off")}>暂不授权</button>
        </div>
        <small>位置将用于 Adex 及相关查询服务。首次使用时，系统可能请求定位权限。</small>
      </section>
    </article>
  );
}

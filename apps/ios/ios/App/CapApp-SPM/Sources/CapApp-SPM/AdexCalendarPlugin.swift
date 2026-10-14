import Capacitor
import EventKit

/// Device-only agenda reader. No write methods, network calls or persisted event cache.
@objc(AdexCalendarPlugin)
public class AdexCalendarPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AdexCalendarPlugin"
    public let jsName = "AdexCalendar"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "request", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "read", returnType: CAPPluginReturnPromise)
    ]
    private let store = EKEventStore()
    private var permission: String {
        let status = EKEventStore.authorizationStatus(for: .event)
        if #available(iOS 17.0, *) {
            if status == .fullAccess { return "GRANTED" }
        } else if status == .authorized { return "GRANTED" }
        if status == .notDetermined { return "NEEDS_PERMISSION" }
        return "DENIED"
    }
    // Only the explicit UI authorization button calls this method. On iOS 17,
    // EventKit requires full access to read; our bridge still exposes no writes.
    @objc public func request(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            let completion: (Bool, Error?) -> Void = { _, error in
                DispatchQueue.main.async {
                    if error != nil { call.reject("CALENDAR_PERMISSION_FAILED"); return }
                    call.resolve(["permission": self.permission])
                }
            }
            if #available(iOS 17.0, *) {
                self.store.requestFullAccessToEvents(completion: completion)
            } else {
                self.store.requestAccess(to: .event, completion: completion)
            }
        }
    }
    @objc public func read(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard self.permission == "GRANTED" else {
                call.resolve(["permission": self.permission, "events": [], "partial": false]); return
            }
            // Bound native work independently of model-generated input. EventKit
            // expands recurring instances across all calendars synced to this phone.
            let start = Calendar.current.startOfDay(for: Date())
            let end = Calendar.current.date(byAdding: .day, value: 7, to: start)!
            let predicate = self.store.predicateForEvents(withStart: start, end: end, calendars: nil)
            let events = self.store.events(matching: predicate).filter { $0.status != .canceled }.sorted { $0.startDate < $1.startDate }
            let iso = ISO8601DateFormatter()
            let day = DateFormatter()
            day.calendar = Calendar(identifier: .gregorian)
            day.locale = Locale(identifier: "en_US_POSIX")
            day.timeZone = .current
            day.dateFormat = "yyyy-MM-dd"
            let rows: [[String: Any]] = events.prefix(200).enumerated().map { index, event in
                let key = event.isAllDay ? "date" : "dateTime"
                var row: [String: Any] = ["id": "\(event.eventIdentifier ?? String(index)):\(event.startDate.timeIntervalSince1970)",
                        "summary": event.title ?? "未命名安排",
                        "start": [key: event.isAllDay ? day.string(from: event.startDate) : iso.string(from: event.startDate)],
                        "end": [key: event.isAllDay ? day.string(from: event.endDate) : iso.string(from: event.endDate)]]
                if let organizer = event.organizer {
                    row["organizer"] = organizer.name ?? organizer.url.absoluteString.replacingOccurrences(of: "mailto:", with: "")
                }
                if let location = event.location, !location.isEmpty { row["location"] = location }
                return row
            }
            call.resolve(["permission": "GRANTED", "events": rows, "partial": events.count > 200])
        }
    }
}

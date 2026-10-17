import Capacitor
import CoreLocation

/// Foreground one-shot approximate location, never background tracking.
@objc(AdexLocationPlugin)
public class AdexLocationPlugin: CAPPlugin, CAPBridgedPlugin, CLLocationManagerDelegate {
    public let identifier = "AdexLocationPlugin"
    public let jsName = "AdexLocation"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "current", returnType: CAPPluginReturnPromise)]
    private var manager: CLLocationManager?
    private var pending: CAPPluginCall?
    private let geocoder = CLGeocoder()
    private var requested = false
    private var resolving = false

    @objc public func current(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard self.pending == nil else { call.reject("LOCATION_BUSY"); return }
            self.pending = call
            self.requested = false
            self.resolving = false
            let manager = CLLocationManager()
            self.manager = manager
            manager.delegate = self
            manager.desiredAccuracy = kCLLocationAccuracyKilometer
            self.authorize(manager)
            DispatchQueue.main.asyncAfter(deadline: .now() + 12) {
                if self.pending === call { self.fail("LOCATION_TIMEOUT") }
            }
        }
    }
    private func authorize(_ manager: CLLocationManager) {
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways:
            if !requested { requested = true; manager.requestLocation() }
        case .denied, .restricted: fail("LOCATION_PERMISSION_DENIED")
        @unknown default: fail("LOCATION_UNAVAILABLE")
        }
    }
    public func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard pending != nil else { return }
        authorize(manager)
    }
    public func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        fail("LOCATION_UNAVAILABLE")
    }
    public func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let call = pending, let fix = locations.last,
              fix.horizontalAccuracy >= 0, abs(fix.timestamp.timeIntervalSinceNow) < 300 else {
            fail("LOCATION_UNAVAILABLE"); return
        }
        guard !resolving else { return }
        resolving = true
        manager.stopUpdatingLocation()
        let approximate = CLLocation(latitude: (fix.coordinate.latitude * 100).rounded() / 100, longitude: (fix.coordinate.longitude * 100).rounded() / 100)
        geocoder.reverseGeocodeLocation(approximate) { places, _ in
            DispatchQueue.main.async {
                guard self.pending === call else { return }
                let place = places?.first
                let label = [place?.administrativeArea, place?.locality, place?.subLocality]
                    .compactMap { $0 }.reduce(into: [String]()) { result, value in
                        if !result.contains(value) { result.append(value) }
                    }.joined(separator: " ")
                self.pending = nil
                self.manager?.delegate = nil
                self.manager = nil
                call.resolve(["latitude": (fix.coordinate.latitude * 100).rounded() / 100,
                              "longitude": (fix.coordinate.longitude * 100).rounded() / 100,
                              "label": String(label.prefix(120)),
                              "observed_at": ISO8601DateFormatter().string(from: fix.timestamp)])
            }
        }
    }
    private func fail(_ code: String) {
        guard let call = pending else { return }
        pending = nil
        manager?.stopUpdatingLocation()
        manager?.delegate = nil
        manager = nil
        geocoder.cancelGeocode()
        call.reject(code)
    }
}

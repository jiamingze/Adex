import Capacitor
import UIKit

/// Private attachment bytes arrive through authenticated App API, never a public URL.
@objc(AdexFilePlugin)
public class AdexFilePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AdexFilePlugin"
    public let jsName = "AdexFile"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "share", returnType: CAPPluginReturnPromise)]

    @objc func share(_ call: CAPPluginCall) {
        guard let encoded = call.getString("base64"), encoded.count <= 35_000_000,
              let bytes = Data(base64Encoded: encoded), bytes.count <= 25 * 1024 * 1024 else {
            call.reject("ATTACHMENT_SIZE_LIMIT"); return
        }
        let name = (call.getString("name") ?? "attachment") as NSString
        let safeName = name.lastPathComponent.components(separatedBy: .controlCharacters).joined()
        guard !safeName.isEmpty, safeName != ".", safeName != ".." else {
            call.reject("INVALID_ATTACHMENT_NAME"); return
        }
        DispatchQueue.main.async {
            guard let presenter = self.bridge?.viewController, presenter.presentedViewController == nil else {
                call.reject("ATTACHMENT_VIEW_BUSY"); return
            }
            let folder = FileManager.default.temporaryDirectory.appendingPathComponent("AdexAttachment-" + UUID().uuidString, isDirectory: true)
            let file = folder.appendingPathComponent(safeName)
            do {
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try bytes.write(to: file, options: .atomic)
            } catch {
                try? FileManager.default.removeItem(at: folder)
                call.reject("ATTACHMENT_SAVE_FAILED"); return
            }
            let activity = UIActivityViewController(activityItems: [file], applicationActivities: nil)
            activity.popoverPresentationController?.sourceView = presenter.view
            activity.popoverPresentationController?.sourceRect = CGRect(x: presenter.view.bounds.midX, y: presenter.view.bounds.midY, width: 1, height: 1)
            activity.completionWithItemsHandler = { _, completed, _, error in
                try? FileManager.default.removeItem(at: folder)
                if error != nil { call.reject("ATTACHMENT_SHARE_FAILED") }
                else { call.resolve(["completed": completed]) }
            }
            presenter.present(activity, animated: true)
        }
    }
}

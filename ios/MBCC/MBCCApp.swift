import SwiftUI

@main
struct MBCCApp: App {
    @StateObject private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(store).tint(Theme.orange)
        }
    }
}


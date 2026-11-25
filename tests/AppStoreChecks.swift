import Foundation

private struct FixtureResponse {
    let status: Int
    let data: Data
    var delay: TimeInterval = 0
}

private final class FixtureProtocol: URLProtocol, @unchecked Sendable {
    typealias Handler = (URLRequest) throws -> FixtureResponse
    private static let lock = NSLock()
    private nonisolated(unsafe) static var route: Handler?
    private nonisolated(unsafe) static var recorded: [URLRequest] = []

    static func respond(using handler: @escaping Handler) {
        lock.lock(); defer { lock.unlock() }
        route = handler
    }

    static var requests: [URLRequest] {
        lock.lock(); defer { lock.unlock() }
        return recorded
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.lock.lock()
        Self.recorded.append(request)
        let handler = Self.route
        Self.lock.unlock()
        do {
            let result = try handler!(request)
            DispatchQueue.global().asyncAfter(deadline: .now() + result.delay) { [self] in
                let response = HTTPURLResponse(url: request.url!, statusCode: result.status,
                                               httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                client?.urlProtocol(self, didLoad: result.data)
                client?.urlProtocolDidFinishLoading(self)
            }
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }
    override func stopLoading() {}
}

private func fixture(_ group: String?, player: String) throws -> Data {
    var snapshot: [String: Any] = [
        "isDemo": false, "season": "Group checks", "updatedAt": "2026-11-25T12:00:00Z",
        "gamesSource": "live_scores_and_games", "players": [player],
        "standings": [["player": player, "correct": 1, "overallScore": 1, "pointDifference": 7]],
        "games": [], "progress": [], "history": [], "careers": [], "seasons": []
    ]
    if let group { snapshot["group"] = group; snapshot["keywordRouting"] = true }
    return try JSONSerialization.data(withJSONObject: snapshot)
}

private let subCode = "FixturePrivateCodeA42"
private let combinedCode = "FixturePrivateCodeB42"

// These are mock API rules, never an application-side lookup table.
private func submittedKeyword(_ request: URLRequest) -> String {
    guard let header = request.value(forHTTPHeaderField: SnapshotConnection.keywordHeader),
          let data = Data(base64Encoded: header) else { return "" }
    return String(data: data, encoding: .utf8) ?? ""
}

private func requestedGroup(_ request: URLRequest) -> String {
    switch submittedKeyword(request).lowercased() {
    case subCode.lowercased(): return "sub"
    case combinedCode.lowercased(): return "default+sub"
    default: return "default"
    }
}

private final class MemoryKeywordStorage: GroupKeywordStorage {
    private var value: String?
    var allowsSaving = true
    func load() -> String? { value }
    @discardableResult func save(_ value: String) -> Bool {
        guard allowsSaving else { return false }
        self.value = value
        return true
    }
}

@main
@MainActor
struct AppStoreChecks {
    static func main() async throws {
        let suite = "MBCC-AppStoreChecks-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        let cache = FileManager.default.temporaryDirectory.appendingPathComponent(suite + ".json")
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [FixtureProtocol.self]
        let session = URLSession(configuration: config)
        defer {
            defaults.removePersistentDomain(forName: suite)
            try? FileManager.default.removeItem(at: cache)
            session.invalidateAndCancel()
        }
        let endpoint = "https://fixture.example/api/snapshot?other=keep"
        let keywords = MemoryKeywordStorage()
        defaults.set(endpoint, forKey: "apiEndpoint")
        defaults.set(false, forKey: "useDemo")
        let store = AppStore(defaults: defaults, session: session, cacheURL: cache, keywordStorage: keywords)
        precondition(store.groupKeyword.isEmpty && store.snapshot == nil)

        FixtureProtocol.respond { request in
            let group = requestedGroup(request)
            return FixtureResponse(status: 200, data: try fixture(group, player: group))
        }
        await store.configure(demo: false, endpoint: endpoint, keyword: "")
        precondition(store.snapshot?.players == ["default"] && store.error == nil)
        precondition(FixtureProtocol.requests.last!.url!.query == "other=keep")
        let mainIdentity = store.connectionIdentity
        await store.configure(demo: false, endpoint: endpoint, keyword: " " + subCode + " ")
        precondition(store.groupKeyword == subCode && store.snapshot?.players == ["sub"])
        precondition(store.connectionIdentity != mainIdentity)
        precondition(defaults.string(forKey: "groupKeyword") == nil && keywords.load() == subCode)
        let cachedJSON = String(data: try Data(contentsOf: cache), encoding: .utf8)!
        precondition(!cachedJSON.contains(subCode) && !cachedJSON.contains(Data(subCode.utf8).base64EncodedString()))
        let restored = AppStore(defaults: defaults, session: session, cacheURL: cache, keywordStorage: keywords)
        precondition(restored.groupKeyword == subCode && restored.snapshot?.players == ["sub"] && restored.isCached)
        await store.configure(demo: false, endpoint: endpoint, keyword: combinedCode)
        precondition(store.snapshot?.group == "default+sub")
        precondition(FixtureProtocol.requests.last!.url!.query == "other=keep")
        precondition(submittedKeyword(FixtureProtocol.requests.last!) == combinedCode)
        let requestCount = FixtureProtocol.requests.count
        await store.configure(demo: false, endpoint: endpoint, keyword: "unknown")
        precondition(FixtureProtocol.requests.count == requestCount + 1)
        precondition(store.groupKeyword == "unknown" && store.snapshot?.players == ["default"] && store.error == nil)
        await store.configure(demo: false, endpoint: endpoint, keyword: subCode)

        let beforeSaveFailure = FixtureProtocol.requests.count
        keywords.allowsSaving = false
        await store.configure(demo: false, endpoint: endpoint, keyword: combinedCode)
        precondition(FixtureProtocol.requests.count == beforeSaveFailure && store.groupKeyword == subCode)
        precondition(store.error!.contains("securely"))
        keywords.allowsSaving = true

        // A failed switch cannot reuse another group's last successful results.
        FixtureProtocol.respond { _ in throw URLError(.notConnectedToInternet) }
        await store.configure(demo: false, endpoint: endpoint, keyword: "")
        precondition(store.snapshot == nil && !store.isCached && store.error != nil)
        let offlineMain = AppStore(defaults: defaults, session: session, cacheURL: cache, keywordStorage: keywords)
        precondition(offlineMain.snapshot == nil)

        // Old APIs without a group field remain valid for main only.
        FixtureProtocol.respond { _ in FixtureResponse(status: 200, data: try fixture(nil, player: "Legacy main")) }
        await store.configure(demo: false, endpoint: endpoint, keyword: "")
        precondition(store.snapshot?.players == ["Legacy main"] && store.error == nil)
        await store.configure(demo: false, endpoint: endpoint, keyword: subCode)
        precondition(store.snapshot == nil && store.error!.contains("private group keywords"))

        // Current-group saved results survive a refresh failure, with no leakage
        // when the selected keyword changes again.
        FixtureProtocol.respond { request in
            FixtureResponse(status: 200, data: try fixture(requestedGroup(request), player: "Sub player"))
        }
        await store.configure(demo: false, endpoint: endpoint, keyword: subCode)
        FixtureProtocol.respond { _ in throw URLError(.notConnectedToInternet) }
        await store.refresh()
        precondition(store.isCached && store.snapshot?.players == ["Sub player"] && store.error != nil)
        let countBeforeDemo = FixtureProtocol.requests.count
        await store.configure(demo: true, endpoint: endpoint, keyword: subCode)
        precondition(store.selectedGroup == .main && FixtureProtocol.requests.count == countBeforeDemo)

        // Personal keywords can share the same main roster while identifying
        // different players. Their saved personalization must stay isolated.
        var personal = try JSONSerialization.jsonObject(with: fixture("default", player: "Alice")) as! [String: Any]
        personal["players"] = ["Alice", "Bob"]
        personal["viewerPlayer"] = "Alice"
        let personalData = try JSONSerialization.data(withJSONObject: personal)
        FixtureProtocol.respond { _ in FixtureResponse(status: 200, data: personalData) }
        await store.configure(demo: false, endpoint: endpoint, keyword: "FixturePersonalCodeA")
        precondition(store.snapshot?.personalizedPlayer == "Alice" && store.snapshot?.players.count == 2)
        FixtureProtocol.respond { _ in throw URLError(.notConnectedToInternet) }
        await store.configure(demo: false, endpoint: endpoint, keyword: "FixturePersonalCodeB")
        precondition(store.snapshot == nil && !store.isCached)

        // Configuration errors intentionally returned by the backend stay useful.
        FixtureProtocol.respond { _ in
            FixtureResponse(status: 409, data: Data("{\"error\":\"Subgroup is not configured\"}".utf8))
        }
        try? FileManager.default.removeItem(at: cache)
        await store.configure(demo: false, endpoint: endpoint, keyword: subCode)
        precondition(store.snapshot == nil && store.error == "Subgroup is not configured")

        // A response from before the switch must not replace the new group or
        // overwrite its cache when its slower request finally completes.
        FixtureProtocol.respond { request in
            let group = requestedGroup(request)
            return FixtureResponse(status: 200, data: try fixture(group, player: group), delay: group == "default" ? 0.15 : 0)
        }
        keywords.save("")
        let switching = AppStore(defaults: defaults, session: session, cacheURL: cache, keywordStorage: keywords)
        let before = FixtureProtocol.requests.count
        let earlier = Task { await switching.refresh() }
        for _ in 0..<1000 {
            if FixtureProtocol.requests.count > before { break }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        precondition(FixtureProtocol.requests.count > before)
        await switching.configure(demo: false, endpoint: endpoint, keyword: subCode)
        await earlier.value
        precondition(switching.groupKeyword == subCode && switching.snapshot?.players == ["sub"])
        precondition(!switching.isLoading && switching.error == nil)
        let afterRace = AppStore(defaults: defaults, session: session, cacheURL: cache, keywordStorage: keywords)
        precondition(afterRace.snapshot?.players == ["sub"] && afterRace.isCached)
        print("AppStore checks passed: private-header requests, server resolution, secure storage, persistence, cache isolation, demo restrictions, old APIs, and switching races.")
    }
}

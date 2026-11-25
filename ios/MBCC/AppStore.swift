import Foundation
import Combine
import CryptoKit
import Security

protocol GroupKeywordStorage {
    func load() -> String?
    @discardableResult func save(_ value: String) -> Bool
}

final class KeychainGroupKeywordStorage: GroupKeywordStorage {
    private var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: Bundle.main.bundleIdentifier ?? "com.mehfoud.MBCC",
         kSecAttrAccount as String: "privateGroupKeyword"]
    }

    func load() -> String? {
        var query = query
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func save(_ value: String) -> Bool {
        if value.isEmpty {
            let status = SecItemDelete(query as CFDictionary)
            return status == errSecSuccess || status == errSecItemNotFound
        }
        let attributes = [kSecValueData as String: Data(value.utf8)]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecSuccess { return true }
        guard status == errSecItemNotFound else { return false }
        var item = query.merging(attributes) { _, new in new }
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        let added = SecItemAdd(item as CFDictionary, nil)
        if added != errSecSuccess { NSLog("MBCC secure keyword storage failed (OSStatus %d)", added) }
        return added == errSecSuccess
    }
}

private final class SnapshotRedirectDelegate: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

@MainActor
final class AppStore: ObservableObject {
    static let defaultEndpoint = "https://mbcc-api-jarvycxodq-ue.a.run.app/api/snapshot"
    @Published private var unfilteredSnapshot: Snapshot?
    @Published var currentPlayersOnly: Bool {
        didSet { defaults.set(currentPlayersOnly, forKey: "currentPlayersOnly") }
    }
    var snapshot: Snapshot? { unfilteredSnapshot?.filteringCurrentPlayers(currentPlayersOnly) }
    @Published private(set) var isLoading = false
    @Published private(set) var error: String?
    @Published private(set) var isDemo: Bool
    @Published private(set) var endpoint: String
    @Published private(set) var groupKeyword: String
    @Published private(set) var isCached = false
    private let defaults: UserDefaults
    private let session: URLSession
    private let cacheURL: URL
    private let keywordStorage: GroupKeywordStorage
    private var generation = 0
    var isSampleData: Bool { isDemo || snapshot?.isDemo == true }
    var selectedGroup: ChallengeGroup { ChallengeGroup(rawValue: snapshot?.group ?? "default") ?? .main }
    private var keywordFingerprint: String {
        SHA256.hash(data: Data(groupKeyword.utf8)).map { String(format: "%02x", $0) }.joined()
    }
    var connectionIdentity: [String] { [isDemo ? "demo" : "api", endpoint, keywordFingerprint] }

    init(defaults: UserDefaults = .standard, session: URLSession = .shared, cacheURL: URL? = nil,
         keywordStorage: GroupKeywordStorage = KeychainGroupKeywordStorage()) {
        self.defaults = defaults
        self.session = session
        self.keywordStorage = keywordStorage
        self.cacheURL = cacheURL ?? FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("mbcc-snapshot.json")
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--ui-testing") {
            defaults.removeObject(forKey: "apiEndpoint")
            defaults.removeObject(forKey: "useDemo")
            defaults.removeObject(forKey: "currentPlayersOnly")
            defaults.removeObject(forKey: "groupKeyword")
            keywordStorage.save("")
        }
        #endif
        let savedEndpoint = defaults.string(forKey: "apiEndpoint") ?? Self.defaultEndpoint
        endpoint = Self.validURL(savedEndpoint).flatMap(SnapshotConnection.snapshotURL)?.absoluteString ?? savedEndpoint
        isDemo = defaults.object(forKey: "useDemo") as? Bool ?? false
        let legacy = defaults.string(forKey: "groupKeyword") ?? ""
        let storedKeyword = SnapshotConnection.normalizedKeyword(keywordStorage.load() ?? (legacy == "default" ? "" : legacy))
        groupKeyword = storedKeyword
        if keywordStorage.save(storedKeyword) { defaults.removeObject(forKey: "groupKeyword") }
        currentPlayersOnly = defaults.object(forKey: "currentPlayersOnly") as? Bool ?? true
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--ui-testing"),
           !ProcessInfo.processInfo.arguments.contains("--live-data") {
            endpoint = ""
            isDemo = true
        }
        #endif
        if isDemo { loadDemo() } else { loadCache() }
    }

    func configure(demo: Bool, endpoint: String, keyword: String = "") async {
        let keyword = SnapshotConnection.normalizedKeyword(keyword)
        guard keywordStorage.save(keyword) else {
            error = "Couldn’t save the group keyword securely. Try saving the connection again."
            return
        }
        generation += 1
        isLoading = false
        unfilteredSnapshot = nil
        error = nil
        isCached = false
        isDemo = demo
        let trimmedEndpoint = endpoint.trimmingCharacters(in: .whitespacesAndNewlines)
        self.endpoint = Self.validURL(trimmedEndpoint).flatMap(SnapshotConnection.snapshotURL)?.absoluteString ?? trimmedEndpoint
        groupKeyword = keyword
        defaults.set(demo, forKey: "useDemo")
        defaults.set(self.endpoint, forKey: "apiEndpoint")
        defaults.removeObject(forKey: "groupKeyword")
        if demo { loadDemo() } else { loadCache(); await refresh() }
    }

    func refresh() async {
        guard !isDemo, !isLoading else { return }
        let requestKeyword = groupKeyword
        guard let baseURL = Self.validURL(endpoint), let url = SnapshotConnection.snapshotURL(from: baseURL) else {
            error = "Add your HTTPS snapshot URL in Data Connection to load MBCC results."
            return
        }
        let requestGeneration = generation
        isLoading = true
        defer { if generation == requestGeneration { isLoading = false } }
        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 60
            request.cachePolicy = .reloadIgnoringLocalCacheData
            request.setValue("application/json", forHTTPHeaderField: "Accept")
            request.setValue(SnapshotConnection.encodedKeyword(requestKeyword), forHTTPHeaderField: SnapshotConnection.keywordHeader)
            let (data, response) = try await session.data(for: request, delegate: SnapshotRedirectDelegate())
            guard let http = response as? HTTPURLResponse else { throw ConnectionError.server }
            if http.statusCode == 409,
               let failure = try? JSONDecoder().decode(BackendError.self, from: data), !failure.error.isEmpty {
                throw ConnectionError.groupUnavailable(String(failure.error.prefix(1000)))
            }
            guard http.statusCode == 200 else { throw ConnectionError.backend(http.statusCode) }
            let loaded = try JSONDecoder().decode(Snapshot.self, from: data)
            guard !loaded.players.isEmpty else { throw ConnectionError.empty }
            guard loaded.isDemo == true || loaded.hasLiveGameSource else { throw ConnectionError.wrongSource }
            guard SnapshotConnection.accepts(loaded, keyword: requestKeyword) else { throw ConnectionError.wrongGroup }
            guard generation == requestGeneration else { return }
            unfilteredSnapshot = loaded
            isCached = false
            error = nil
            if let cache = try? JSONEncoder().encode(CachedSnapshot(endpoint: url.absoluteString, keywordFingerprint: keywordFingerprint, snapshot: loaded)) {
                try? cache.write(to: cacheURL, options: .atomic)
            }
        } catch is CancellationError {
            return
        } catch {
            guard generation == requestGeneration else { return }
            isCached = snapshot != nil
            switch error as? ConnectionError {
            case .wrongSource:
                self.error = "This connection is still serving the old game list. Update the MBCC service and try again."
            case .wrongGroup:
                self.error = "Update the MBCC backend to recognize private group keywords."
            case .groupUnavailable(let message):
                self.error = message
            case .backend(let status):
                self.error = "The MBCC backend couldn’t load the selected group (HTTP \(status)). Check its spreadsheet settings and backend logs."
            default:
                self.error = snapshot == nil
                    ? "Couldn’t load MBCC results. Check the connection URL and try again."
                    : "Couldn’t refresh. Showing the last saved results."
            }
        }
    }

    static func validURL(_ value: String) -> URL? {
        guard let url = URL(string: value), let host = url.host,
              url.user == nil, url.password == nil,
              url.fragment == nil else { return nil }
        if url.scheme == "https" { return url }
        #if DEBUG
        if url.scheme == "http", ["localhost", "127.0.0.1", "::1"].contains(host) { return url }
        #endif
        return nil
    }

    private func loadDemo() {
        do {
            guard let url = Bundle.main.url(forResource: "demo", withExtension: "json") else {
                throw ConnectionError.empty
            }
            var data = try Data(contentsOf: url)
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("--ui-testing"),
               let fixture = ProcessInfo.processInfo.environment["MBCC_TEST_SNAPSHOT"] {
                data = Data(fixture.utf8)
            }
            #endif
            unfilteredSnapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            error = nil
        } catch { self.error = "The demo data could not be loaded." }
    }

    private func loadCache() {
        guard let baseURL = Self.validURL(endpoint), let url = SnapshotConnection.snapshotURL(from: baseURL),
              let data = try? Data(contentsOf: cacheURL),
              let cached = try? JSONDecoder().decode(CachedSnapshot.self, from: data),
              cached.endpoint == url.absoluteString, cached.snapshot.hasLiveGameSource,
              cached.keywordFingerprint == keywordFingerprint || groupKeyword.isEmpty && cached.keywordFingerprint == nil,
              SnapshotConnection.accepts(cached.snapshot, keyword: groupKeyword) else { return }
        unfilteredSnapshot = cached.snapshot
        isCached = true
    }

    private struct CachedSnapshot: Codable { let endpoint: String; let keywordFingerprint: String?; let snapshot: Snapshot }
    private struct BackendError: Decodable { let error: String }
    private enum ConnectionError: Error {
        case server, empty, wrongSource, wrongGroup, backend(Int), groupUnavailable(String)
    }
}


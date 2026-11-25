import Foundation

extension String {
    var groupDisplayName: String {
        for suffix in [" [Main]", " [Sub]"] where hasSuffix(suffix) {
            return String(dropLast(suffix.count))
        }
        return self
    }
}

enum ChallengeGroup: String, CaseIterable {
    case main = "default"
    case sub = "sub"
    case combined = "default+sub"

    var title: String {
        switch self {
        case .main: return "Main group"
        case .sub: return "Subgroup"
        case .combined: return "Main group + subgroup"
        }
    }

}

enum SnapshotConnection {
    static let keywordHeader = "X-MBCC-Keyword"

    static func normalizedKeyword(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func encodedKeyword(_ value: String) -> String? {
        let keyword = normalizedKeyword(value)
        return keyword.isEmpty ? nil : Data(keyword.utf8).base64EncodedString()
    }

    static func snapshotURL(from endpoint: URL) -> URL? {
        guard var parts = URLComponents(url: endpoint, resolvingAgainstBaseURL: false) else { return nil }
        // Preserve other encoded connection parameters, including duplicate
        // keys, while replacing any manually entered group parameter.
        let items = (parts.percentEncodedQueryItems ?? []).filter {
            !["group", "keyword"].contains($0.name.removingPercentEncoding ?? $0.name)
        }
        parts.percentEncodedQueryItems = items.isEmpty ? nil : items
        return parts.url
    }

    static func accepts(_ snapshot: Snapshot, keyword: String) -> Bool {
        guard ChallengeGroup(rawValue: snapshot.group ?? "default") != nil else { return false }
        if normalizedKeyword(keyword).isEmpty { return snapshot.group == nil || snapshot.group == "default" }
        return snapshot.keywordRouting == true
    }
}

struct Snapshot: Codable {
    let isDemo: Bool?
    let season: String
    let updatedAt: String
    var players: [String]
    var standings: [Standing]
    var games: [BowlGame]
    var progress: [ProgressPoint]
    var history: [HistoryEntry]
    var careers: [CareerEntry]
    let seasons: [SeasonEntry]
    let gamesSource: String?
    let todaysUpdate: DailyUpdate?
    let updates: [DailyUpdate]?
    var playoffStandings: [PlayoffStanding]?
    let playoffStandingsError: String?
    let group: String?
    let playoffHistoryScope: String?
    let keywordRouting: Bool?
    let viewerPlayer: String?
    var personalizedPlayer: String? {
        guard let viewerPlayer, players.contains(viewerPlayer) else { return nil }
        return viewerPlayer
    }
    var updatePosts: [DailyUpdate] { updates ?? todaysUpdate.map { [$0] } ?? [] }
    var hasLiveGameSource: Bool { gamesSource == "live_scores_and_games" }

    var completed: Int { games.filter(\.isFinal).count }
    var remaining: Int { games.count - completed }

    func filteringCurrentPlayers(_ currentOnly: Bool) -> Snapshot {
        guard currentOnly else { return self }
        // Match the web app: career Active, then history Current, then the
        // season roster for players who have no historical status yet.
        var status: [String: Bool] = [:]
        for row in history { status[row.player] = row.current }
        for row in careers { status[row.player] = row.active }
        var current = Set(status.compactMap { $0.value ? $0.key : nil })
        current.formUnion(players.filter { status[$0] == nil })
        var filtered = self
        filtered.players = players.filter { current.contains($0) }
        filtered.standings = standings.filter { current.contains($0.player) }
        filtered.history = history.filter { current.contains($0.player) }
        filtered.careers = careers.filter { current.contains($0.player) }
        filtered.playoffStandings = playoffStandings?.filter { current.contains($0.player) }
        filtered.games = games.map { game in
            var game = game
            game.picks = game.picks.filter { current.contains($0.key) }
            return game
        }
        filtered.progress = progress.map { point in
            ProgressPoint(gameIndex: point.gameIndex,
                          correct: point.correct.filter { current.contains($0.key) },
                          pointDifference: point.pointDifference.filter { current.contains($0.key) })
        }
        return filtered
    }

    var tracksPlayoffHistory: Bool { group != "sub" && playoffHistoryScope != "none" }
    var mainGroupPlayoffHistoryOnly: Bool { group == "default+sub" }
    var playoffHistoryUnavailable: Bool {
        guard tracksPlayoffHistory, let error = playoffStandingsError else { return false }
        return !(mainGroupPlayoffHistoryOnly && error == "All-time playoff standings unavailable for: Subgroup.")
    }

    var rankedPlayoffStandings: [PlayoffStanding] {
        guard tracksPlayoffHistory else { return [] }
        return (playoffStandings ?? []).sorted {
            if $0.correctPlayoff != $1.correctPlayoff { return ($0.correctPlayoff ?? -1) > ($1.correctPlayoff ?? -1) }
            if $0.correctUnknownPlayoff != $1.correctUnknownPlayoff { return ($0.correctUnknownPlayoff ?? -1) > ($1.correctUnknownPlayoff ?? -1) }
            return $0.player.lowercased() < $1.player.lowercased()
        }
    }

    var playoffRounds: [PlayoffRound] {
        PlayoffRound.allCases
    }

    func playoffGames(in round: PlayoffRound) -> [BowlGame] {
        games.filter { PlayoffRound.classify($0.name) == round }.sorted {
            $0.date == $1.date ? $0.id < $1.id : $0.date < $1.date
        }
    }

    var championships: [ChampionshipRecord] {
        let names = Set(players + history.map(\.player) + careers.map(\.player))
        return names.map { player in
            let seasons = Dictionary(grouping: history.filter { $0.player == player && $0.isWinner }, by: \.season)
            let fullWins = seasons.values.filter { entries in
                entries.contains { $0.award.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "winner" }
            }.count
            return ChampionshipRecord(player: player, fullWins: fullWins, sharedWins: seasons.count - fullWins)
        }.sorted {
            if $0.trophyCount != $1.trophyCount { return $0.trophyCount > $1.trophyCount }
            return $0.player.localizedStandardCompare($1.player) == .orderedAscending
        }
    }

    func ranked(by margin: Bool) -> [Standing] {
        standings.sorted {
            let lhs = margin ? $0.pointDifference : $0.overallScore
            let rhs = margin ? $1.pointDifference : $1.overallScore
            return lhs == rhs ? $0.player < $1.player : lhs > rhs
        }
    }

    // Port of the Streamlit pairwise best-case comparison. This is not an
    // exhaustive solver of mutually dependent playoff bracket outcomes.
    func elimination(for player: String) -> EliminationResult {
        let pending = games.filter { !$0.isFinal }
        let possible = pending.filter { game in
            guard let pick = game.picks[player], !pick.isEmpty else { return false }
            return game.homeTeam == "TBD" || game.awayTeam == "TBD"
                || pick == game.homeTeam || pick == game.awayTeam
        }
        let comparisons = players.map { other in
            let current = standings.first { $0.player == other }?.correct ?? 0
            let shared = possible.filter { $0.picks[other] == $0.picks[player] }.count
            return BestCase(player: other, correct: current + shared)
        }
        let own = comparisons.first { $0.player == player }?.correct ?? 0
        return EliminationResult(best: own, comparisons: comparisons,
                                 eliminated: comparisons.contains { $0.correct > own })
    }
}

struct PlayoffStanding: Codable, Identifiable {
    var id: String { player }
    let player: String
    let correctPlayoff: Int?
    let correctUnknownPlayoff: Int?
}

enum PlayoffRound: Int, CaseIterable, Identifiable {
    case first, quarterfinals, semifinals, championship
    var id: Int { rawValue }
    var title: String { ["First round", "Quarterfinals", "Semifinals", "Championship"][rawValue] }

    static func classify(_ name: String) -> PlayoffRound? {
        let normalized = name.lowercased().components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { !$0.isEmpty }.joined(separator: " ")
        guard normalized.contains("college football playoff") || normalized.split(separator: " ").contains("cfp") else { return nil }
        if normalized.contains("quarterfinal") || normalized.contains("quarter final") { return .quarterfinals }
        if normalized.contains("semifinal") || normalized.contains("semi final") { return .semifinals }
        if normalized.contains("championship") { return .championship }
        if normalized.contains("first round") || normalized.contains("1st round") { return .first }
        return nil
    }
}

struct DailyUpdate: Codable {
    let title: String
    let message: String
    let publishedDate: String
    let youtubeURL: String?

    var dateLabel: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: publishedDate) else { return publishedDate }
        formatter.locale = .current
        formatter.dateStyle = .long
        return formatter.string(from: date)
    }

    var video: YouTubeVideo? { youtubeURL.flatMap(YouTubeVideo.init) }
}

struct YouTubeVideo {
    let id: String
    let url: URL
    var thumbnailURL: URL { URL(string: "https://i.ytimg.com/vi/\(id)/hqdefault.jpg")! }

    init?(_ value: String) {
        guard let components = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              components.scheme?.lowercased() == "https",
              components.user == nil, components.password == nil,
              components.port == nil || components.port == 443,
              let host = components.host?.lowercased(), let url = components.url else { return nil }
        let parts = components.path.split(separator: "/").map(String.init)
        let candidate: String?
        if ["youtu.be", "www.youtu.be"].contains(host), parts.count == 1 {
            candidate = parts.first
        } else if ["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"].contains(host) {
            if parts == ["watch"] {
                candidate = components.queryItems?.first { $0.name == "v" }?.value
            } else if parts.count == 2, ["shorts", "embed", "live"].contains(parts[0]) {
                candidate = parts[1]
            } else { candidate = nil }
        } else { return nil }
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        guard let candidate, candidate.count == 11,
              candidate.unicodeScalars.allSatisfy({ allowed.contains($0) }) else { return nil }
        id = candidate
        self.url = url
    }
}

struct Standing: Codable, Identifiable {
    var id: String { player }
    let player: String
    let correct: Int
    let overallScore: Double
    let pointDifference: Double
}

enum PickOutcome: String {
    case pending, correct, incorrect
}

struct BowlGame: Codable, Identifiable {
    let id: String
    let name: String
    let startTime: String
    let venue: String
    let network: String
    let homeTeam: String
    let awayTeam: String
    let homeScore: Int?
    let awayScore: Int?
    let pointDifference: Int?
    let winner: String?
    let upset: Bool?
    let unanimous: Bool?
    let focusTeam: String?
    let espnID: String?
    var picks: [String: String]
    let live: LiveScore?
    let verification: String?
    let verificationReason: String?
    let gameVerification: String?
    let gameVerificationReason: String?
    let fieldVerification: [String: FieldVerification]?
    let kickoffTimeKnown: Bool?

    var displayedHomeScore: Int? { homeScore }
    var displayedAwayScore: Int? { awayScore }
    var gameStatus: String { live?.status.uppercased() ?? (isFinal ? "FINAL" : "SCHEDULED") }
    func verificationStatus(at now: Date = Date(), forGame: Bool = false) -> String {
        let keys = forGame ? ["startTime", "homeTeam", "awayTeam"] : ["homeScore", "awayScore", "pointDifference"]
        if let checks = fieldVerification {
            guard keys.allSatisfy({ checks[$0] != nil }) else { return "unavailable" }
            let statuses = keys.map { checks[$0]!.currentStatus(at: now) }
            return ["unavailable", "mismatch", "pending"].first { statuses.contains($0) } ?? "verified"
        }
        if forGame { return "unavailable" }
        guard let live, let fetched = live.fetchedDate else {
            return "unavailable"
        }
        let age = now.timeIntervalSince(fetched)
        let completed = live.status == "final" && verification == "verified" && gameVerification == "verified"
        guard age >= -60, completed || age <= (live.status == "final" ? 48 * 3600 : 600) else { return "unavailable" }
        return verification ?? "unavailable"
    }
    func verificationLabel(at now: Date = Date(), forGame: Bool = false) -> String {
        switch verificationStatus(at: now, forGame: forGame) {
        case "verified": return forGame ? "Game matches" : "Scores match"
        case "mismatch": return forGame ? "Game mismatch" : "Score mismatch"
        case "pending": return forGame ? "Game not verified" : "Scores not verified"
        default: return forGame ? "Game not verified" : "Scores not verified"
        }
    }

    var date: Date { ISO8601DateFormatter().date(from: startTime) ?? .distantPast }
    var isFinal: Bool {
        (live == nil || live?.status == "final") && winner != nil && winner != "TBD" && winner != ""
    }
    func pickOutcome(for player: String?) -> PickOutcome? {
        guard let player, let pick = picks[player], !pick.isEmpty else { return nil }
        guard isFinal else { return .pending }
        return pick == winner ? .correct : .incorrect
    }
    var kickoffText: String {
        kickoffTimeKnown == false ? date.formatted(date: .abbreviated, time: .omitted) + " · Time TBD"
            : date.formatted(date: .abbreviated, time: .shortened)
    }
    static let checkedFields: [(key: String, label: String)] = [
        ("startTime", "Kickoff"), ("awayTeam", "Away team"), ("homeTeam", "Home team"),
        ("awayScore", "Away score"), ("homeScore", "Home score"), ("pointDifference", "Score difference")
    ]
    var espnURL: URL? {
        guard let espnID, !espnID.isEmpty,
              espnID.allSatisfy(\.isNumber) else { return nil }
        return URL(string: "https://www.espn.com/college-football/game?gameId=\(espnID)")
    }
}

struct FieldVerification: Codable {
    let status: String
    let value: String
    let originalValue: String
    let source: String
    let reason: String
    let updatedAt: String?
    let maxAgeSeconds: Int?

    func currentStatus(at now: Date = Date()) -> String {
        if status == "pending", updatedAt == nil { return "pending" }
        guard let fetched = LiveScore.date(updatedAt),
              now.timeIntervalSince(fetched) >= -60 else { return "unavailable" }
        if let maxAgeSeconds, now.timeIntervalSince(fetched) > Double(maxAgeSeconds) { return "unavailable" }
        return status
    }
}

struct LiveScore: Codable {
    let status: String
    let homeScore: Int?
    let awayScore: Int?
    let source: String
    let updatedAt: String?
    var fetchedDate: Date? {
        Self.date(updatedAt)
    }
    static func date(_ value: String?) -> Date? {
        guard let value else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: value) ?? ISO8601DateFormatter().date(from: value)
    }
}

struct ProgressPoint: Codable, Identifiable {
    var id: Int { gameIndex }
    let gameIndex: Int
    let correct: [String: Double]
    let pointDifference: [String: Double]
}

struct HistoryEntry: Codable, Identifiable {
    var id: String { season + "|" + player }
    let season: String
    let player: String
    let correct: Int
    let games: Int
    let percentage: Double
    let award: String
    let current: Bool
    var isWinner: Bool { ["winner", "co-winner"].contains(award.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()) }
}

struct ChampionshipRecord: Identifiable {
    var id: String { player }
    let player: String
    let fullWins: Int
    let sharedWins: Int
    var trophyCount: Double { Double(fullWins) + Double(sharedWins) / 2 }
}

struct CareerEntry: Codable, Identifiable {
    var id: String { player }
    let player: String
    let wins: Int
    let losses: Int
    let percentage: Double
    let active: Bool
}

struct SeasonEntry: Codable, Identifiable {
    var id: String { season }
    let season: String
    let wins: Int
    let losses: Int
    let percentage: Double
}

struct BestCase: Identifiable {
    var id: String { player }
    let player: String
    let correct: Int
}

struct EliminationResult {
    let best: Int
    let comparisons: [BestCase]
    let eliminated: Bool
}

extension Double {
    var scoreText: String { formatted(.number.precision(.fractionLength(0...3))) }
    var percentText: String { formatted(.percent.precision(.fractionLength(1))) }
}


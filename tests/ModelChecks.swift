import Foundation

@main
struct ModelChecks {
    static func main() throws {
        let demo = URL(fileURLWithPath: CommandLine.arguments[1])
        let original = try Data(contentsOf: demo)
        let snapshot = try JSONDecoder().decode(Snapshot.self, from: original)
        precondition(snapshot.players.count == 10)
        precondition(snapshot.completed == 5 && snapshot.remaining == 3)
        precondition(snapshot.progress.last?.gameIndex == 5)
        precondition(snapshot.games[0].date != .distantPast)
        precondition(!snapshot.hasLiveGameSource) // The old/demo contract is not a live-tab cache.
        precondition(snapshot.todaysUpdate == nil) // Compatible with existing servers and caches.
        precondition(snapshot.updatePosts.isEmpty)
        precondition(snapshot.playoffStandings == nil && snapshot.rankedPlayoffStandings.isEmpty)
        precondition(snapshot.tracksPlayoffHistory && !snapshot.mainGroupPlayoffHistoryOnly)
        var historyTotals = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        historyTotals["playoffStandings"] = [
            ["player": "Zoe", "correctPlayoff": 3, "correctUnknownPlayoff": 1],
            ["player": "Bob", "correctPlayoff": 3, "correctUnknownPlayoff": 2],
            ["player": "Missing", "correctPlayoff": NSNull(), "correctUnknownPlayoff": NSNull()],
            ["player": "Zero", "correctPlayoff": 0, "correctUnknownPlayoff": 0],
            ["player": "Alice", "correctPlayoff": 3, "correctUnknownPlayoff": 2],
        ]
        let allTime = try decode(historyTotals).rankedPlayoffStandings
        precondition(allTime.map(\.player) == ["Alice", "Bob", "Zoe", "Zero", "Missing"])
        precondition(allTime.last?.correctPlayoff == nil)
        var subgroupHistory = historyTotals
        subgroupHistory["group"] = "sub"
        subgroupHistory["playoffStandingsError"] = "Old backend could not load history"
        let subgroup = try decode(subgroupHistory)
        precondition(!subgroup.tracksPlayoffHistory && !subgroup.playoffHistoryUnavailable)
        precondition(subgroup.rankedPlayoffStandings.isEmpty)
        subgroupHistory.removeValue(forKey: "group")
        subgroupHistory["playoffHistoryScope"] = "none"
        let explicitScope = try decode(subgroupHistory)
        precondition(!explicitScope.tracksPlayoffHistory)
        var combinedHistory = historyTotals
        combinedHistory["group"] = "default+sub"
        combinedHistory["playoffStandingsError"] = "All-time playoff standings unavailable for: Subgroup."
        let combined = try decode(combinedHistory)
        precondition(combined.tracksPlayoffHistory && combined.mainGroupPlayoffHistoryOnly)
        precondition(!combined.playoffHistoryUnavailable)
        precondition(combined.rankedPlayoffStandings.count == allTime.count)
        combinedHistory["playoffStandingsError"] = "Main-group history failed"
        let failedMainHistory = try decode(combinedHistory)
        precondition(failedMainHistory.playoffHistoryUnavailable)
        // The app-wide player setting follows the web filter and preserves
        // source snapshots, game results, and historical playoff totals.
        var filterObject = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        var filterCareers = filterObject["careers"] as! [[String: Any]]
        filterCareers[0]["active"] = false // Career status takes precedence over history.
        filterObject["careers"] = filterCareers
        filterObject["playoffStandings"] = [
            ["player": "Christopher", "correctPlayoff": 40, "correctUnknownPlayoff": 8],
            ["player": "Elise", "correctPlayoff": 30, "correctUnknownPlayoff": 7],
            ["player": "Former", "correctPlayoff": 20, "correctUnknownPlayoff": 0],
        ]
        let fullRoster = try decode(filterObject)
        let currentRoster = fullRoster.filteringCurrentPlayers(true)
        precondition(!currentRoster.players.contains("Christopher"))
        precondition(currentRoster.players.contains("Elise"))
        precondition(currentRoster.standings.allSatisfy { $0.player != "Christopher" })
        precondition(currentRoster.history.allSatisfy { $0.player != "Christopher" })
        precondition(currentRoster.careers.allSatisfy { $0.player != "Christopher" })
        precondition(currentRoster.games.allSatisfy { $0.picks["Christopher"] == nil })
        precondition(currentRoster.progress.allSatisfy { $0.correct["Christopher"] == nil && $0.pointDifference["Christopher"] == nil })
        precondition(currentRoster.championships.allSatisfy { $0.player != "Christopher" })
        precondition(currentRoster.elimination(for: "Elise").comparisons.allSatisfy { $0.player != "Christopher" })
        precondition(currentRoster.rankedPlayoffStandings.map(\.player) == ["Elise"])
        precondition(currentRoster.rankedPlayoffStandings[0].correctPlayoff == 30)
        precondition(currentRoster.rankedPlayoffStandings[0].correctUnknownPlayoff == 7)
        precondition(currentRoster.games.map(\.id) == fullRoster.games.map(\.id))
        precondition(currentRoster.completed == fullRoster.completed)
        precondition(currentRoster.seasons.map(\.wins) == fullRoster.seasons.map(\.wins))
        precondition(fullRoster.players.contains("Christopher"))
        precondition(fullRoster.filteringCurrentPlayers(false).rankedPlayoffStandings.map(\.player) == ["Christopher", "Elise", "Former"])
        filterObject["careers"] = []
        var filterHistory = filterObject["history"] as! [[String: Any]]
        filterHistory = filterHistory.filter { $0["player"] as? String == "Christopher" }
        for index in filterHistory.indices { filterHistory[index]["current"] = false }
        filterObject["history"] = filterHistory
        let fallbackRoster = try decode(filterObject).filteringCurrentPlayers(true)
        precondition(!fallbackRoster.players.contains("Christopher"))
        precondition(fallbackRoster.players.contains("Emma")) // New roster player without history.
        precondition(snapshot.playoffRounds.allSatisfy { snapshot.playoffGames(in: $0).isEmpty })
        for (name, round) in [("CFP First-Round", PlayoffRound.first), ("CFP 1st Round", .first),
                              ("College Football Playoff Quarterfinal at the Rose Bowl", .quarterfinals),
                              ("CFP Semi-final", .semifinals), ("College Football Playoff National Championship", .championship)] {
            precondition(PlayoffRound.classify(name) == round)
        }
        for name in ["Cotton Bowl", "Orange Bowl", "Chalice Championship", "FCS National Championship"] {
            precondition(PlayoffRound.classify(name) == nil)
        }
        var bracketObject = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        let baseGame = (bracketObject["games"] as! [[String: Any]])[0]
        let roundNames = ["First Round", "Quarterfinal", "Semifinal", "National Championship"]
        var bracketGames: [[String: Any]] = []
        for (index, count) in [4, 4, 2, 1].enumerated() {
            for number in 0..<count {
                var game = baseGame
                game["id"] = "\(index)-\(number)"
                game["name"] = "College Football Playoff \(roundNames[index])"
                game["startTime"] = "2026-12-\(10 + number)T20:00:00-05:00"
                bracketGames.insert(game, at: 0)
            }
        }
        bracketObject["games"] = bracketGames + [baseGame]
        let bracket = try decode(bracketObject)
        precondition(bracket.playoffRounds.map { bracket.playoffGames(in: $0).count } == [4, 4, 2, 1])
        precondition(bracket.playoffGames(in: .first).map(\.id) == ["0-0", "0-1", "0-2", "0-3"])
        for link in [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",
            "https://youtu.be/dQw4w9WgXcQ?si=shared",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/shorts/dQw4w9WgXcQ",
            "https://youtube.com/live/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ] {
            let video = YouTubeVideo(link)!
            precondition(video.id == "dQw4w9WgXcQ")
            precondition(video.url.absoluteString == link)
            precondition(video.thumbnailURL.absoluteString == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg")
        }
        for link in ["http://youtube.com/watch?v=dQw4w9WgXcQ", "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
                     "https://youtube.com@evil.test/watch?v=dQw4w9WgXcQ", "https://user@youtube.com/watch?v=dQw4w9WgXcQ",
                     "https://youtube.com/watch?v=short", "https://youtu.be/dQw4w9WgXc!", "javascript:alert(1)",
                     "https://youtube.com/playlist?list=example", "https://youtu.be/dQw4w9WgXcQ/extra"] {
            precondition(YouTubeVideo(link) == nil)
        }
        var updateObject = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        updateObject["todaysUpdate"] = ["title": "Bowl briefing", "message": "The latest from MBCC.",
                                       "publishedDate": "2026-11-20", "youtubeURL": "https://youtu.be/dQw4w9WgXcQ"]
        let update = try decode(updateObject).todaysUpdate!
        precondition(update.title == "Bowl briefing" && update.video != nil)
        precondition(!update.dateLabel.isEmpty)
        let legacyUpdate = try decode(updateObject)
        precondition(legacyUpdate.updatePosts.count == 1) // Earlier single-post API.
        updateObject["updates"] = [
            ["title": "Newest post", "message": "First paragraph.\n\nSecond paragraph.",
             "publishedDate": "2026-11-20", "youtubeURL": "https://youtu.be/dQw4w9WgXcQ"],
            ["title": "Previous post", "message": "Earlier news", "publishedDate": "2026-11-19"],
        ]
        let posts = try decode(updateObject).updatePosts
        precondition(posts.map(\.title) == ["Newest post", "Previous post"])
        precondition(posts[0].message.contains("\n\n") && posts[1].video == nil)
        updateObject["updates"] = []
        let clearedUpdates = try decode(updateObject)
        precondition(clearedUpdates.updatePosts.isEmpty) // Explicitly cleared feed.
        precondition(snapshot.ranked(by: false).first!.overallScore >= snapshot.ranked(by: false).last!.overallScore)
        precondition(snapshot.ranked(by: true).first!.pointDifference >= snapshot.ranked(by: true).last!.pointDifference)

        // Trophy totals count each championship season once and retain non-winners.
        var trophyObject = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        trophyObject["players"] = ["Nicholas", "Joseph", "No wins"]
        trophyObject["careers"] = []
        func championship(_ season: String, _ player: String, _ award: String) -> [String: Any] {
            ["season": season, "player": player, "award": award, "correct": 1,
             "games": 1, "percentage": 1.0, "current": player != "Former winner"]
        }
        trophyObject["history"] = [
            championship("First", "Nicholas", "Co-Winner"),
            championship("First", "Joseph", "Co-Winner"),
            championship("Second", "Joseph", "Winner"),
            championship("Second", "Joseph", "Winner"),
            championship("Third", "Former winner", " Winner "),
        ]
        let trophies = try decode(trophyObject).championships
        precondition(trophies.map(\.player) == ["Joseph", "Former winner", "Nicholas", "No wins"])
        precondition(trophies[0].fullWins == 1 && trophies[0].sharedWins == 1 && trophies[0].trophyCount == 1.5)
        precondition(trophies[2].fullWins == 0 && trophies[2].sharedWins == 1 && trophies[2].trophyCount == 0.5)
        precondition(trophies[3].trophyCount == 0)

        // A checked comparison can describe an ongoing game without finalizing it.
        var liveObject = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        var ongoing = (liveObject["games"] as! [[String: Any]])[5]
        ongoing["winner"] = NSNull()
        ongoing["homeScore"] = 0
        ongoing["awayScore"] = 7
        ongoing["pointDifference"] = 7
        ongoing["live"] = ["status": "live", "homeScore": 0, "awayScore": 7,
                           "source": "ESPN", "updatedAt": "2026-10-29T18:00:00.123Z"]
        ongoing["verification"] = "verified"
        ongoing["fieldVerification"] = [
            "homeScore": ["status": "verified", "value": "0", "originalValue": "0", "source": "scores",
                          "reason": "Matches", "updatedAt": "2026-10-29T18:00:00.123Z", "maxAgeSeconds": 300],
            "awayScore": ["status": "verified", "value": "7", "originalValue": "7", "source": "scores",
                          "reason": "Matches", "updatedAt": "2026-10-29T18:00:00.123Z", "maxAgeSeconds": 300],
            "pointDifference": ["status": "verified", "value": "7", "originalValue": "7", "source": "scores",
                          "reason": "Matches", "updatedAt": "2026-10-29T18:00:00.123Z", "maxAgeSeconds": 300],
            "homeTeam": ["status": "verified", "value": "Home", "originalValue": "Home", "source": "unlive_games",
                      "reason": "Matches", "updatedAt": "2026-10-29T18:00:00Z", "maxAgeSeconds": 172800],
            "awayTeam": ["status": "verified", "value": "Away", "originalValue": "Away", "source": "unlive_games",
                      "reason": "Matches", "updatedAt": "2026-10-29T18:00:00Z", "maxAgeSeconds": 172800],
            "startTime": ["status": "verified", "value": "Kickoff", "originalValue": "Kickoff", "source": "unlive_games",
                      "reason": "Matches", "updatedAt": "2026-10-29T18:00:00Z", "maxAgeSeconds": 172800],
        ]
        liveObject["games"] = [ongoing]
        let liveGame = try decode(liveObject).games[0]
        let checkedAt = ISO8601DateFormatter().date(from: "2026-10-29T18:01:00Z")!
        precondition(!liveGame.isFinal)
        precondition(liveGame.gameStatus == "LIVE")
        precondition(liveGame.displayedHomeScore == 0)
        precondition(liveGame.verificationStatus(at: checkedAt) == "verified")
        precondition(liveGame.verificationLabel(at: checkedAt) == "Scores match")
        precondition(liveGame.verificationStatus(at: checkedAt.addingTimeInterval(301)) == "unavailable")
        precondition(liveGame.fieldVerification!["homeScore"]!.currentStatus(at: checkedAt) == "verified")
        precondition(liveGame.fieldVerification!["awayScore"]!.currentStatus(at: checkedAt) == "verified")
        precondition(liveGame.fieldVerification!["homeScore"]!.currentStatus(at: checkedAt.addingTimeInterval(301)) == "unavailable")
        precondition(liveGame.verificationStatus(at: checkedAt.addingTimeInterval(301), forGame: true) == "verified")
        precondition(liveGame.verificationLabel(at: checkedAt, forGame: true) == "Game matches")
        precondition(liveGame.pointDifference == 7)
        var checks = ongoing["fieldVerification"] as! [String: [String: Any]]
        checks["pointDifference"]!["status"] = "mismatch"
        checks["pointDifference"]!["originalValue"] = "8"
        ongoing["fieldVerification"] = checks
        liveObject["games"] = [ongoing]
        let mismatch = try decode(liveObject).games[0]
        precondition(mismatch.verificationStatus(at: checkedAt) == "mismatch")
        precondition(mismatch.verificationStatus(at: checkedAt, forGame: true) == "verified")
        precondition(Set(BowlGame.checkedFields.map(\.key)) == Set(["startTime", "homeTeam", "awayTeam", "homeScore", "awayScore", "pointDifference"]))
        // Confirmed finals no longer need polling or a freshness countdown.
        ongoing["live"] = ["status": "final", "homeScore": 0, "awayScore": 7,
                           "source": "ESPN", "updatedAt": "2026-10-29T18:00:00.123Z"]
        ongoing["winner"] = ongoing["awayTeam"]
        ongoing["fieldVerification"] = checks.mapValues { check -> [String: Any] in
            var confirmed = check
            confirmed["status"] = "verified"
            confirmed["maxAgeSeconds"] = NSNull()
            return confirmed
        }
        liveObject["games"] = [ongoing]
        let confirmed = try decode(liveObject).games[0]
        precondition(confirmed.isFinal)
        let nextMonth = checkedAt.addingTimeInterval(30 * 86400)
        precondition(confirmed.verificationStatus(at: nextMonth) == "verified")
        precondition(confirmed.verificationStatus(at: nextMonth, forGame: true) == "verified")
        // A fresh import shows two unchecked groups, with no fabricated scores.
        ongoing["live"] = ["status": "scheduled", "source": "ESPN", "updatedAt": NSNull(),
                           "homeScore": NSNull(), "awayScore": NSNull()]
        ongoing["homeScore"] = NSNull(); ongoing["awayScore"] = NSNull(); ongoing["winner"] = NSNull()
        ongoing["fieldVerification"] = checks.mapValues { check -> [String: Any] in
            var pending = check
            pending["status"] = "pending"
            pending["updatedAt"] = NSNull()
            return pending
        }
        liveObject["games"] = [ongoing]
        liveObject["gamesSource"] = "live_scores_and_games"
        let imported = try decode(liveObject)
        precondition(imported.hasLiveGameSource)
        precondition(imported.games[0].verificationLabel(at: checkedAt) == "Scores not verified")
        precondition(imported.games[0].verificationLabel(at: checkedAt, forGame: true) == "Game not verified")
        precondition(snapshot.games[0].verificationStatus(at: checkedAt) == "unavailable")

        // Distinct final-game picks: a trailing player can tie, so remains alive.
        var data = try JSONSerialization.jsonObject(with: original) as! [String: Any]
        data["players"] = ["Alice", "Bob"]
        data["standings"] = [
            ["player": "Alice", "correct": 0, "overallScore": 0, "pointDifference": 0],
            ["player": "Bob", "correct": 1, "overallScore": 1, "pointDifference": 7],
        ]
        var game = (data["games"] as! [[String: Any]])[5]
        game["homeTeam"] = "Home"; game["awayTeam"] = "Away"
        game["picks"] = ["Alice": "Home", "Bob": "Away"]
        data["games"] = [game]
        var subject = try decode(data)
        precondition(!subject.elimination(for: "Alice").eliminated)
        precondition(subject.elimination(for: "Alice").best == 1)

        // Shared pick gives the leader the same extra win: trailing player eliminated.
        game["picks"] = ["Alice": "Home", "Bob": "Home"]
        data["games"] = [game]
        subject = try decode(data)
        precondition(subject.elimination(for: "Alice").eliminated)

        // Impossible bracket picks cannot increase the player's best case.
        game["picks"] = ["Alice": "Eliminated team", "Bob": "Home"]
        data["games"] = [game]
        subject = try decode(data)
        precondition(subject.elimination(for: "Alice").best == 0)
        // Unset bracket slots still allow a potential pick.
        game["homeTeam"] = "TBD"
        data["games"] = [game]
        subject = try decode(data)
        precondition(subject.elimination(for: "Alice").best == 1)

        // The backend contract and bundled fixture must both decode in Swift.
        if CommandLine.arguments.count > 2 {
            let path = URL(fileURLWithPath: CommandLine.arguments[2])
            let adapted = try JSONDecoder().decode(Snapshot.self, from: Data(contentsOf: path))
            precondition(adapted.players == ["Alice", "Bob"])
            precondition(adapted.games[0].espnURL != nil)
            precondition(adapted.games[1].homeScore == nil)
        }
        if CommandLine.arguments.count > 3 {
            let path = URL(fileURLWithPath: CommandLine.arguments[3])
            let liveData = try Data(contentsOf: path)
            let live = try JSONDecoder().decode(Snapshot.self, from: liveData)
            precondition(live.isDemo == false)
            precondition(!live.players.isEmpty && !live.games.isEmpty && !live.history.isEmpty)
            precondition(Set(live.games.map(\.id)).count == live.games.count)
            precondition(live.games.allSatisfy { $0.date != .distantPast })
            precondition(Set(live.players) == Set(live.standings.map(\.player)))
            let raw = try JSONSerialization.jsonObject(with: liveData) as! [String: Any]
            precondition(live.history.count == (raw["history"] as! [[String: Any]]).count)
            for player in live.players {
                precondition(live.elimination(for: player).comparisons.count == live.players.count)
            }
            print("Live contract verified: \(live.players.count) players, \(live.games.count) games, \(live.history.count) history rows.")
        }
        print("Model checks passed: decoding, rankings, counts, elimination ties, shared picks and playoff slots.")
    }

    static func decode(_ object: [String: Any]) throws -> Snapshot {
        try JSONDecoder().decode(Snapshot.self, from: JSONSerialization.data(withJSONObject: object))
    }
}

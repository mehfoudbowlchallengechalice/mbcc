import XCTest

final class MBCCUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()
    }

    private func openTab(_ title: String) {
        let tab = app.tabBars.buttons[title]
        if tab.exists { tab.tap() }
        else {
            app.tabBars.buttons["More"].tap()
            app.staticTexts[title].firstMatch.tap()
        }
    }

    func testCoreScreensAndGamePicks() {
        XCTAssertTrue(app.staticTexts["DEMO · Sample results, not real standings"].waitForExistence(timeout: 10))
        app.swipeUp()
        let bowl = app.staticTexts["Chalice Kickoff Bowl"].firstMatch
        XCTAssertTrue(bowl.waitForExistence(timeout: 5))
        bowl.tap()
        XCTAssertTrue(app.staticTexts["Everyone’s picks"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Christopher"].firstMatch.exists)
        app.navigationBars.buttons.firstMatch.tap()

        app.tabBars.buttons["Standings"].tap()
        XCTAssertTrue(app.staticTexts["The race for the chalice"].exists)
        app.buttons["Point difference"].tap()
        XCTAssertTrue(app.staticTexts["Christopher"].firstMatch.exists)

        app.tabBars.buttons["Season"].tap()
        XCTAssertTrue(app.staticTexts["How the season unfolds"].exists)
        for _ in 0..<5 {
            if app.staticTexts["Elimination check"].isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(app.staticTexts["Elimination check"].isHittable)
        XCTAssertTrue(app.staticTexts["Not yet eliminated"].exists || app.staticTexts["Eliminated"].exists)

        openTab("Bracket")
        XCTAssertTrue(app.staticTexts["The road to the championship"].exists)
        XCTAssertTrue(app.staticTexts["The playoff bracket isn’t available yet"].exists)

        openTab("History")
        XCTAssertTrue(app.staticTexts["A tradition worth keeping"].exists)
        XCTAssertFalse(app.switches["Include former players"].exists)
        app.switches["Show more than winners"].tap()

        openTab("Info")
        XCTAssertTrue(app.staticTexts["One chalice. All the bragging rights."].exists)
    }

    func testGroupKeywordValidationAndPersistence() {
        XCTAssertTrue(app.staticTexts["DEMO · Sample results, not real standings"].waitForExistence(timeout: 10))
        app.buttons["dataConnection"].tap()
        let keyword = app.secureTextFields["groupKeyword"]
        XCTAssertTrue(keyword.waitForExistence(timeout: 5))
        XCTAssertFalse((keyword.value as? String ?? "").contains("default"))
        XCTAssertFalse(app.textFields["groupKeyword"].exists)
        keyword.tap()
        keyword.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 7) + "unknown")
        XCTAssertTrue(app.buttons["saveConnection"].isEnabled)
        XCTAssertFalse(app.staticTexts["Showing: Main group"].exists)
        XCTAssertFalse(app.staticTexts["Group keyword not recognized."].exists)
        XCTAssertFalse(app.staticTexts["Enter default, sub, or default+sub."].exists)
        keyword.tap()
        keyword.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 7) + " SUB ")
        XCTAssertFalse(app.staticTexts["Showing: Subgroup"].exists)
        keyword.typeText("\n")
        let demoSwitch = app.switches["Explore demo data"]
        demoSwitch.coordinate(withNormalizedOffset: CGVector(dx: 0.92, dy: 0.5)).tap()
        XCTAssertEqual(demoSwitch.value as? String, "0")
        let endpoint = app.textFields["snapshotURL"]
        endpoint.tap()
        endpoint.typeText("http://localhost:1/api/snapshot\n")
        app.buttons["saveConnection"].tap()
        XCTAssertTrue(app.staticTexts["Connect to MBCC"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["DEMO · Sample results, not real standings"].exists)
        app.terminate()
        app.launchArguments = []
        app.launch()
        app.buttons["dataConnection"].tap()
        XCTAssertTrue(app.secureTextFields["groupKeyword"].waitForExistence(timeout: 5))
        let savedKeyword = app.secureTextFields["groupKeyword"].value as? String ?? ""
        XCTAssertFalse(savedKeyword.isEmpty)
        XCTAssertNotEqual(savedKeyword, "Enter keyword")
        XCTAssertFalse(savedKeyword.lowercased().contains("sub"))
        XCTAssertFalse(app.staticTexts["Showing: Subgroup"].exists)
        XCTAssertEqual(app.switches["Explore demo data"].value as? String, "0")
    }

    func testPersonalSchedulePicksAndFullStandings() throws {
        app.terminate()
        func game(_ id: String, _ home: String, _ away: String, _ pick: String, _ winner: String?) -> [String: Any] {
            ["id": id, "name": id, "startTime": "2099-12-12T20:00:00-05:00",
             "venue": "Sample stadium", "network": "Test",
             "homeTeam": home, "awayTeam": away, "homeScore": winner == nil ? NSNull() : 14,
             "awayScore": winner == nil ? NSNull() : 7, "winner": winner as Any? ?? NSNull(),
             "picks": ["Alice": pick, "Bob": home]]
        }
        let fixture: [String: Any] = [
            "isDemo": true, "season": "Personal picks preview", "updatedAt": "2026-11-25T12:00:00Z",
            "players": ["Alice", "Bob"], "viewerPlayer": "Alice", "group": "default", "keywordRouting": true,
            "standings": [["player": "Alice", "correct": 1, "overallScore": 1.0, "pointDifference": 7.0],
                          ["player": "Bob", "correct": 2, "overallScore": 2.0, "pointDifference": 14.0]],
            "games": [game("Correct Pick Bowl", "Correct Choice", "Other One", "Correct Choice", "Correct Choice"),
                      game("Incorrect Pick Bowl", "Other Two", "Incorrect Choice", "Incorrect Choice", "Other Two"),
                      game("Pending Pick Bowl", "Pending Choice", "Other Three", "Pending Choice", nil)],
            "progress": [], "history": [], "careers": [], "seasons": []
        ]
        app.launchEnvironment["MBCC_TEST_SNAPSHOT"] = String(data: try JSONSerialization.data(withJSONObject: fixture), encoding: .utf8)!
        app.launch()
        for label in ["Correct Choice, your pick, correct", "Incorrect Choice, your pick, incorrect", "Pending Choice, your pick, pending"] {
            for _ in 0..<8 {
                if app.staticTexts[label].isHittable { break }
                app.swipeUp()
            }
            XCTAssertTrue(app.staticTexts[label].exists)
        }
        openTab("Standings")
        XCTAssertTrue(app.staticTexts["Alice"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["Bob"].firstMatch.exists)
    }

    func testCurrentPlayerSettingAppliesToStandingsPlayoffsAndHistory() throws {
        app.terminate()
        let fixture: [String: Any] = [
            "isDemo": true, "season": "Player filter preview", "updatedAt": "2026-11-23T12:00:00Z",
            "players": ["Alice", "Bob"],
            "standings": [
                ["player": "Alice", "correct": 3, "overallScore": 3.0, "pointDifference": 7.0],
                ["player": "Bob", "correct": 4, "overallScore": 4.0, "pointDifference": 8.0],
            ],
            "games": [], "progress": [],
            "history": [
                ["player": "Alice", "season": "2025", "correct": 3, "games": 4, "percentage": 0.75, "award": "", "current": true],
                ["player": "Bob", "season": "2025", "correct": 4, "games": 4, "percentage": 1.0, "award": "Winner", "current": false],
            ],
            "careers": [], "seasons": [],
            "playoffStandings": [
                ["player": "Alice", "correctPlayoff": 30, "correctUnknownPlayoff": 7],
                ["player": "Bob", "correctPlayoff": 40, "correctUnknownPlayoff": 8],
            ],
        ]
        app.launchEnvironment["MBCC_TEST_SNAPSHOT"] = String(data: try JSONSerialization.data(withJSONObject: fixture), encoding: .utf8)!
        app.launch()
        openTab("Standings")
        XCTAssertTrue(app.staticTexts["Alice"].firstMatch.waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts["Bob"].exists)
        app.buttons["dataConnection"].tap()
        let setting = app.switches["currentPlayersOnly"]
        XCTAssertTrue(setting.waitForExistence(timeout: 5))
        XCTAssertEqual(setting.value as? String, "1")
        setting.tap()
        app.buttons["Cancel"].tap()
        XCTAssertTrue(app.staticTexts["Bob"].firstMatch.waitForExistence(timeout: 5))
        openTab("Bracket")
        XCTAssertTrue(app.staticTexts["All-time playoff standings"].exists)
        XCTAssertTrue(app.staticTexts["Bob"].exists)
        XCTAssertTrue(app.staticTexts["40"].exists)
        app.buttons["dataConnection"].tap()
        XCTAssertEqual(app.switches["currentPlayersOnly"].value as? String, "0")
        app.switches["currentPlayersOnly"].tap()
        app.buttons["Cancel"].tap()
        XCTAssertFalse(app.staticTexts["Bob"].exists)
        XCTAssertTrue(app.staticTexts["30"].exists)
        openTab("History")
        XCTAssertFalse(app.switches["Include former players"].exists)
        XCTAssertFalse(app.staticTexts["Bob"].exists)
        app.buttons["dataConnection"].tap()
        app.switches["currentPlayersOnly"].tap()
        app.buttons["saveConnection"].tap()
        app.terminate()
        app.launchArguments = [] // A regular launch retains the saved filter.
        app.launch()
        app.buttons["dataConnection"].tap()
        XCTAssertTrue(app.switches["currentPlayersOnly"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.switches["currentPlayersOnly"].value as? String, "0")
    }

    func testPlayoffBracketGameDetailsAndPicks() throws {
        app.terminate()
        let game: [String: Any] = [
            "id": "playoff-1", "name": "College Football Playoff First Round Game",
            "startTime": "2026-12-18T20:00:00-05:00", "venue": "Sample Stadium", "network": "ESPN",
            "homeTeam": "Virginia Tech", "awayTeam": "Tulane", "homeScore": 0, "awayScore": 7,
            "winner": "Tulane", "picks": ["Alice": "Tulane", "Bob": "Virginia Tech"]
        ]
        let fixture: [String: Any] = ["isDemo": true, "season": "Playoff preview", "updatedAt": "2026-11-23T12:00:00Z",
            "players": ["Alice", "Bob"], "standings": [], "games": [game], "progress": [],
            "history": [], "careers": [], "seasons": []]
        app.launchEnvironment["MBCC_TEST_SNAPSHOT"] = String(data: try JSONSerialization.data(withJSONObject: fixture), encoding: .utf8)!
        app.launch()
        openTab("Bracket")
        XCTAssertTrue(app.staticTexts["The road to the championship"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.scrollViews["playoffBracket"].exists)
        app.buttons["Show picks for"].tap()
        app.buttons["Alice"].tap()
        XCTAssertTrue(app.staticTexts["Pick: Tulane"].exists)
        XCTAssertTrue(app.staticTexts["Correct"].exists)
        app.staticTexts["College Football Playoff First Round Game"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Everyone’s picks"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Alice"].firstMatch.exists)
    }

    func testTodaysUpdatePage() throws {
        app.terminate()
        let fixture: [String: Any] = [
            "isDemo": true, "season": "MBCC preview", "updatedAt": "2026-11-20T12:00:00Z",
            "players": [], "standings": [], "games": [], "progress": [], "history": [], "careers": [], "seasons": [],
            "updates": [["title": "A new season. A new chase.",
                             "message": "Your daily dose of bowl season. Catch up on the latest MBCC news before kickoff.",
                             "publishedDate": "2026-11-20", "youtubeURL": "https://youtu.be/dQw4w9WgXcQ"],
                        ["title": "Yesterday around the chalice", "message": "An earlier post with its own video.",
                         "publishedDate": "2026-11-19", "youtubeURL": "https://youtu.be/abcdefghijk"]]
        ]
        app.launchEnvironment["MBCC_TEST_SNAPSHOT"] = String(data: try JSONSerialization.data(withJSONObject: fixture), encoding: .utf8)!
        app.launch()
        XCTAssertTrue(app.staticTexts["A new season. A new chase."].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Your daily dose of bowl season. Catch up on the latest MBCC news before kickoff."].exists)
        XCTAssertTrue(app.descendants(matching: .any)["updateVideo"].firstMatch.exists)
        XCTAssertFalse(app.staticTexts["Yesterday around the chalice"].exists)
        let livePreview = XCTAttachment(screenshot: app.screenshot())
        livePreview.name = "Full latest update at the top of Live"
        livePreview.lifetime = .keepAlways
        add(livePreview)
        let entry = app.buttons["todaysUpdate"]
        for _ in 0..<6 {
            if entry.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(entry.isHittable)
        entry.tap()
        XCTAssertTrue(app.navigationBars["Today’s Update"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["A new season. A new chase."].exists)
        XCTAssertTrue(app.descendants(matching: .any)["updateVideo"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["Opens in YouTube or your browser."].exists)
        let preview = XCTAttachment(screenshot: app.screenshot())
        preview.name = "Today’s Update video page"
        preview.lifetime = .keepAlways
        add(preview)
        for _ in 0..<6 {
            if app.staticTexts["Yesterday around the chalice"].isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(app.staticTexts["Yesterday around the chalice"].isHittable)
        XCTAssertTrue(app.staticTexts["An earlier post with its own video."].exists)
        let archive = XCTAttachment(screenshot: app.screenshot())
        archive.name = "Previous update in the blog feed"
        archive.lifetime = .keepAlways
        add(archive)
    }

    func testTodaysUpdateEmptyState() {
        let entry = app.buttons["todaysUpdate"]
        XCTAssertTrue(entry.waitForExistence(timeout: 10))
        entry.tap()
        XCTAssertTrue(app.staticTexts["No update yet"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.descendants(matching: .any)["updateVideo"].firstMatch.exists)
    }

    func testConnectionValidationAndNoSilentDemoFallback() {
        app.buttons["dataConnection"].tap()
        let toggle = app.switches["Explore demo data"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 5))
        toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.92, dy: 0.5)).tap()
        XCTAssertEqual(toggle.value as? String, "0")
        let field = app.textFields["snapshotURL"]
        field.tap()
        field.typeText("not-a-url")
        XCTAssertFalse(app.buttons["saveConnection"].isEnabled)
        field.tap()
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 9))
        field.typeText("http://localhost:1/api/snapshot")
        XCTAssertTrue(app.buttons["saveConnection"].isEnabled)
        app.buttons["saveConnection"].tap()
        XCTAssertTrue(app.staticTexts["Connect to MBCC"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["DEMO · Sample results, not real standings"].exists)
    }

    func testTwoVerificationChecks() throws {
        app.terminate()
        let fetched = ISO8601DateFormatter().string(from: Date())
        func check(_ value: String, _ original: String, _ status: String, _ source: String) -> [String: Any] {
            ["status": status, "value": value, "originalValue": original, "source": source,
             "reason": status == "verified" ? "Matches the original entry." : "Differs from the original entry.",
             "updatedAt": fetched, "maxAgeSeconds": 300]
        }
        let game: [String: Any] = [
            "id": "espn:123", "name": "Verification Test Bowl", "startTime": "2099-12-12T12:00:00-05:00",
            "venue": "Changed venue", "network": "ABC", "homeTeam": "Home", "awayTeam": "Away",
            "homeScore": 14, "awayScore": 7, "pointDifference": 7, "winner": NSNull(), "upset": true, "unanimous": true,
            "focusTeam": "Home", "espnID": "123", "picks": ["Alice": "Home"],
            "live": ["status": "live", "homeScore": 14, "awayScore": 7, "source": "Test", "updatedAt": fetched],
            "verification": "mismatch", "verificationReason": "See each score.",
            "fieldVerification": ["startTime": check("Kickoff", "Kickoff", "verified", "unlive_games"),
                "homeTeam": check("Home", "Home", "verified", "unlive_games"),
                "awayTeam": check("Away", "Away", "verified", "unlive_games"),
                "homeScore": check("14", "14", "verified", "scores"),
                "awayScore": check("7", "0", "mismatch", "scores"),
                "pointDifference": check("7", "14", "mismatch", "scores")]
        ]
        let fixture: [String: Any] = ["isDemo": true, "season": "Verification test", "updatedAt": fetched,
            "players": ["Alice"], "standings": [], "games": [game], "progress": [], "history": [],
            "careers": [], "seasons": [], "gamesSource": "live_scores_and_games"]
        app.launchEnvironment["MBCC_TEST_SNAPSHOT"] = String(data: try JSONSerialization.data(withJSONObject: fixture), encoding: .utf8)!
        app.launch()
        XCTAssertTrue(app.staticTexts["Verification Test Bowl"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Game matches"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["Score mismatch"].firstMatch.exists)
        XCTAssertFalse(app.images["Home score: verified"].exists)
        XCTAssertFalse(app.images["Upset game: verified"].exists)
        let card = XCTAttachment(screenshot: app.screenshot())
        card.name = "Game and score verification"
        card.lifetime = .keepAlways
        add(card)
        app.staticTexts["Verification Test Bowl"].tap()
        XCTAssertTrue(app.staticTexts["Compare with original entries"].waitForExistence(timeout: 5))
        for _ in 0..<6 {
            if app.staticTexts["scores: 0"].isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(app.staticTexts["Live: 7"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["scores: 0"].exists)
        let comparison = XCTAttachment(screenshot: app.screenshot())
        comparison.name = "Original score comparison"
        comparison.lifetime = .keepAlways
        add(comparison)
    }

    func testImportedGamesStartUnverified() throws {
        app.terminate()
        let fetched = ISO8601DateFormatter().string(from: Date())
        var checks: [String: [String: Any]] = [:]
        for field in ["startTime", "homeTeam", "awayTeam", "homeScore", "awayScore", "pointDifference"] {
            checks[field] = ["status": "pending", "value": "—", "originalValue": "—",
                             "source": field.contains("Team") || field == "startTime" ? "unlive_games" : "scores",
                             "reason": "Waiting for the first automatic check.",
                             "updatedAt": NSNull(), "maxAgeSeconds": 600]
        }
        let game: [String: Any] = [
            "id": "espn:401874421", "name": "Cricket Celebration Bowl", "startTime": "2026-12-12T12:00:00-05:00",
            "venue": "Mercedes-Benz Stadium", "network": "ABC", "homeTeam": "TBD", "awayTeam": "TBD",
            "homeScore": NSNull(), "awayScore": NSNull(), "pointDifference": NSNull(), "winner": NSNull(),
            "upset": NSNull(), "unanimous": NSNull(), "focusTeam": NSNull(), "espnID": "401874421", "picks": [:],
            "live": ["status": "scheduled", "source": "ESPN", "updatedAt": NSNull(),
                     "homeScore": NSNull(), "awayScore": NSNull()],
            "verification": "pending", "gameVerification": "pending", "fieldVerification": checks]
        let fixture: [String: Any] = ["isDemo": true, "season": "MBCC 15 · 2026–27", "updatedAt": fetched,
                                     "players": ["Alice"], "standings": [], "games": [game], "progress": [],
                                     "history": [], "careers": [], "seasons": [], "gamesSource": "live_scores_and_games"]
        app.launchEnvironment["MBCC_TEST_SNAPSHOT"] = String(data: try JSONSerialization.data(withJSONObject: fixture), encoding: .utf8)!
        app.launch()
        XCTAssertTrue(app.staticTexts["Cricket Celebration Bowl"].waitForExistence(timeout: 10))
        app.staticTexts["Cricket Celebration Bowl"].tap()
        XCTAssertTrue(app.staticTexts["Game not verified"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Scores not verified"].exists)
        XCTAssertFalse(app.staticTexts["Game matches"].exists)
        XCTAssertFalse(app.staticTexts["Scores match"].exists)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Imported game and scores unverified"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func testLiveBackendConnection() {
        app.terminate()
        app.launchArguments = ["--ui-testing", "--live-data"]
        app.launch()
        app.tabBars.buttons["Standings"].tap()
        XCTAssertTrue(app.staticTexts["The race for the chalice"].waitForExistence(timeout: 65))
        XCTAssertTrue(app.staticTexts["Christopher"].firstMatch.exists)
        XCTAssertFalse(app.staticTexts["DEMO · Sample results, not real standings"].exists)
        XCTAssertFalse(app.staticTexts["Connect to MBCC"].exists)

        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Live MBCC standings"
        screenshot.lifetime = .keepAlways
        add(screenshot)

        openTab("History")
        XCTAssertTrue(app.staticTexts["Player season breakdown"].exists)
        XCTAssertTrue(app.switches["Show more than winners"].exists)
        app.switches["Show more than winners"].tap()

        app.buttons["dataConnection"].tap()
        let field = app.textFields["snapshotURL"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        XCTAssertEqual(field.value as? String, "https://mbcc-api-jarvycxodq-ue.a.run.app/api/snapshot")
        XCTAssertEqual(app.switches["Explore demo data"].value as? String, "0")
    }
}

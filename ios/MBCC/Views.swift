import SwiftUI
import Charts

struct RootView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.scenePhase) private var scenePhase
    @State private var showConnection = false

    var body: some View {
        TabView {
            tab("Live", icon: "sportscourt", tag: "live") { LiveView() }
            tab("Standings", icon: "list.number", tag: "standings") { StandingsView() }
            tab("Bracket", icon: "trophy.fill", tag: "bracket") { PlayoffBracketView() }
            tab("Season", icon: "chart.xyaxis.line", tag: "season") { SeasonView() }
            tab("History", icon: "trophy", tag: "history") { HistoryView() }
            tab("Info", icon: "info.circle", tag: "info") { InformationView() }
        }
        .id(store.connectionIdentity)
        .sheet(isPresented: $showConnection) { ConnectionView() }
        .task {
            await store.refresh()
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(60)) } catch { break }
                if scenePhase == .active { await store.refresh() }
            }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await store.refresh() } }
        }
    }

    private func tab<Content: View>(_ title: String, icon: String, tag: String,
                                   @ViewBuilder content: () -> Content) -> some View {
        NavigationStack {
            Group {
                if store.snapshot != nil {
                    content()
                } else {
                    VStack(spacing: 20) {
                        if store.isLoading { ProgressView("Loading MBCC…") }
                        else {
                            ContentUnavailableView("Connect to MBCC", systemImage: "network",
                                description: Text(store.error ?? "Open Data Connection to configure your results or explore demo data."))
                            Button("Data Connection") { showConnection = true }.buttonStyle(.borderedProminent)
                            Button("Try again") { Task { await store.refresh() } }
                        }
                    }.padding()
                }
            }
            .background(Theme.background)
            .navigationTitle(title == "Live" ? "MBCC" : title)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showConnection = true } label: { Image(systemName: "gearshape") }
                        .accessibilityLabel("Data Connection")
                        .accessibilityIdentifier("dataConnection")
                }
            }
            .safeAreaInset(edge: .top, spacing: 0) {
                if store.isSampleData {
                    HStack(spacing: 6) {
                        Image(systemName: "sparkles")
                        Text("DEMO · Sample results, not real standings")
                    }.font(.caption.weight(.medium)).frame(maxWidth: .infinity).padding(8)
                        .background(Theme.orange.opacity(0.10)).foregroundStyle(Theme.orange)
                } else if let error = store.error {
                    Text(error).font(.caption).frame(maxWidth: .infinity).padding(8)
                        .background(Color.yellow.opacity(0.18))
                } else if store.isCached {
                    Text("Saved results · Refreshing when connected")
                        .font(.caption).frame(maxWidth: .infinity).padding(8)
                        .background(Color.yellow.opacity(0.18))
                }
            }
        }
        .tabItem { Label(title, systemImage: icon) }
        .accessibilityIdentifier("tab_\(tag)")
    }
}

struct LiveView: View {
    @EnvironmentObject private var store: AppStore
    @State private var filter = "Today"
    private let filters = ["Today", "Future", "All"]

    private func filtered(_ data: Snapshot) -> [BowlGame] {
        let ordered = data.games.sorted { $0.date < $1.date }
        if filter == "All" { return ordered }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = EasternTime.zone
        let start = calendar.startOfDay(for: Date())
        let future = ordered.filter { $0.date >= start }
        if filter == "Future" { return future }
        guard let first = future.first else { return [] }
        return future.filter { calendar.isDate($0.date, inSameDayAs: first.date) }
    }

    var body: some View {
        if let data = store.snapshot {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 18) {
                    Card {
                        Label("Today’s Update", systemImage: "megaphone.fill")
                            .font(.headline).foregroundStyle(Theme.orange)
                        if let latest = data.updatePosts.first {
                            UpdatePostView(update: latest, isLatest: true)
                        } else {
                            Text("No update yet").font(.title3.bold())
                            Text("Check back here for the latest MBCC news and videos.")
                                .foregroundStyle(.secondary)
                        }
                        Divider()
                        NavigationLink { TodaysUpdateView() } label: {
                            HStack {
                                Text("View all updates").font(.headline)
                                Spacer()
                                Image(systemName: "chevron.right").font(.caption.bold())
                            }
                            .foregroundStyle(Theme.orange)
                            .padding(.vertical, 4)
                            .contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("todaysUpdate")
                    }

                    VStack(alignment: .leading, spacing: 18) {
                        HStack {
                            Text("BOWL SEASON").font(.caption.weight(.bold)).tracking(2)
                            Spacer()
                            Image(systemName: "trophy.fill").foregroundStyle(Color.orange)
                        }
                        Text(data.season).font(.system(.largeTitle, design: .rounded, weight: .bold))
                        Text("Every game. Every pick. One chalice.").font(.subheadline).foregroundStyle(.white.opacity(0.75))
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text("\(data.completed)").font(.system(.largeTitle, design: .rounded, weight: .bold)).monospacedDigit()
                            Text("games in").foregroundStyle(.white.opacity(0.7))
                            Spacer()
                            Text("\(data.remaining) to go").font(.subheadline.bold())
                        }
                        ProgressView(value: Double(data.completed), total: Double(max(data.games.count, 1)))
                            .tint(.orange).accessibilityLabel("Season completion")
                    }.padding(24).foregroundStyle(.white)
                        .background(Theme.navy, in: RoundedRectangle(cornerRadius: 26))

                    if let leader = data.ranked(by: false).first {
                        Card {
                            HStack(spacing: 12) {
                                PlayerAvatar(player: leader.player)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text("SETTING THE PACE").font(.caption2.bold()).foregroundStyle(Theme.orange)
                                    PlayerName(player: leader.player).font(.headline)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 3) {
                                    StandingScore(standing: leader, font: .title2)
                                    Text("correct picks").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    SectionHeading(title: "The games", caption: data.personalizedPlayer.map { "Picks for \($0.groupDisplayName)" } ?? "Scores and everyone’s picks, in one place.")
                    if data.personalizedPlayer != nil {
                        Text("Your pick is bold. Final results: solid green = correct; dotted gray = incorrect.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Picker("Show games", selection: $filter) {
                        ForEach(filters, id: \.self) { Text($0) }
                    }.pickerStyle(.segmented)
                    if filter == "Today" {
                        Text("Today shows the next game day when there are no games today. All dates and times use Eastern Time (ET).")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    let games = filtered(data)
                    if games.isEmpty {
                        EmptyCard(title: "No upcoming games", message: "Switch to All to see this season’s results and picks.")
                        Button("See all games") { filter = "All" }.buttonStyle(.bordered)
                    }
                    ForEach(games) { game in
                        NavigationLink { GameDetailView(game: game) } label: {
                            GameCard(game: game, viewer: data.personalizedPlayer)
                        }.buttonStyle(.plain)
                    }
                    updatedLabel(data)
                }.padding(20)
            }.refreshable { await store.refresh() }
                .onAppear {
                    if filtered(data).isEmpty { filter = "All" }
                }
        }
    }
}

struct PlayoffBracketView: View {
    @EnvironmentObject private var store: AppStore
    @State private var player: String? = nil
    @State private var initializedPlayer = false

    var body: some View {
        if let data = store.snapshot {
            let games = data.playoffRounds.flatMap { data.playoffGames(in: $0) }
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    SectionHeading(title: "The road to the championship", caption: data.season)
                    if games.isEmpty {
                        EmptyCard(title: "The playoff bracket isn’t available yet",
                                  message: "Games will appear here when the schedule includes playoff rounds.")
                    } else {
                        Picker("Show picks for", selection: $player) {
                            Text("Results only").tag(nil as String?)
                            ForEach(data.players, id: \.self) { PlayerName(player: $0).tag(Optional($0)) }
                        }.pickerStyle(.menu)
                        Text("\(games.filter(\.isFinal).count) of \(games.count) playoff games complete · Swipe sideways to see every round.")
                            .font(.caption).foregroundStyle(.secondary)
                        ScrollView(.horizontal) {
                            HStack(alignment: .top, spacing: 20) {
                                ForEach(data.playoffRounds) { round in
                                    VStack(alignment: .leading, spacing: 16) {
                                        VStack(alignment: .leading, spacing: 6) {
                                            Text("ROUND \(round.rawValue + 1)").font(.caption2.bold()).tracking(2)
                                                .foregroundStyle(Theme.orange)
                                            Text(round.title).font(.title3.bold())
                                            Rectangle().fill(Theme.orange).frame(height: 2)
                                        }
                                        let entries = data.playoffGames(in: round)
                                        if entries.isEmpty {
                                            EmptyCard(title: "Awaiting the schedule", message: "This round will appear when games are added.")
                                        }
                                        ForEach(entries) { game in
                                            NavigationLink {
                                                GameDetailView(game: game)
                                            } label: {
                                                PlayoffGameCard(game: game, player: player)
                                            }.buttonStyle(.plain)
                                                .accessibilityHint("Opens game details and everyone’s picks")
                                        }
                                    }.frame(width: 280)
                                }
                            }.padding(.vertical, 4)
                        }
                        .accessibilityIdentifier("playoffBracket")
                        Text("Matchups update with the published schedule. Games are shown in kickoff order within each round.")
                            .font(.caption).foregroundStyle(.secondary)
                        if data.playoffGames(in: .championship).count == 1,
                           let final = data.playoffGames(in: .championship).first, final.isFinal, let winner = final.winner {
                            Card {
                                Label("National champion: \(winner)", systemImage: "trophy.fill")
                                    .font(.headline).foregroundStyle(Theme.orange)
                            }
                        }
                    }
                    PlayoffStandingsTable(standings: data.rankedPlayoffStandings, unavailable: data.playoffHistoryUnavailable,
                                          tracksHistory: data.tracksPlayoffHistory)
                    updatedLabel(data)
                }.padding(20)
            }.refreshable { await store.refresh() }
                .onAppear {
                    if !initializedPlayer { player = data.personalizedPlayer; initializedPlayer = true }
                }
                .onChange(of: data.personalizedPlayer) { old, new in
                    if player == old { player = new }
                }
                .onChange(of: data.players) { _, players in
                    if let player, !players.contains(player) { self.player = nil }
                }
        }
    }
}

private struct PlayoffStandingsTable: View {
    let standings: [PlayoffStanding]
    let unavailable: Bool
    let tracksHistory: Bool
    @State private var sortColumn = SortColumn.playoff
    @State private var ascending = false

    private enum SortColumn { case user, playoff, unknown }

    private var sortedStandings: [PlayoffStanding] {
        standings.sorted { lhs, rhs in
            if sortColumn == .user {
                return ascending ? lhs.player.localizedStandardCompare(rhs.player) == .orderedAscending
                    : lhs.player.localizedStandardCompare(rhs.player) == .orderedDescending
            }
            let first = sortColumn == .playoff ? lhs.correctPlayoff : lhs.correctUnknownPlayoff
            let second = sortColumn == .playoff ? rhs.correctPlayoff : rhs.correctUnknownPlayoff
            if first != second {
                guard let first else { return false }
                guard let second else { return true }
                return ascending ? first < second : first > second
            }
            if sortColumn == .playoff && lhs.correctUnknownPlayoff != rhs.correctUnknownPlayoff {
                return (lhs.correctUnknownPlayoff ?? -1) > (rhs.correctUnknownPlayoff ?? -1)
            }
            return lhs.player.localizedStandardCompare(rhs.player) == .orderedAscending
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionHeading(title: "All-time playoff standings")
            if !tracksHistory {
                EmptyCard(title: "No playoff history", message: "All-time playoff history is not tracked for these results.")
            } else if unavailable {
                EmptyCard(title: "Couldn’t load all-time playoff standings", message: "Pull to refresh and try again.")
            } else if standings.isEmpty {
                EmptyCard(title: "All-time playoff standings aren’t available yet", message: "Check back for historical playoff results.")
            } else {
                let entries = sortedStandings
                Text("All-time correct picks. Tap a heading to sort.").font(.caption).foregroundStyle(.secondary)
                VStack(spacing: 0) {
                    HStack(alignment: .top, spacing: 10) {
                        heading("User", column: .user, alignment: .leading)
                        heading("Correct\nplayoff games", column: .playoff, alignment: .trailing)
                        heading("Correct unknown\nplayoff games", column: .unknown, alignment: .trailing)
                    }.padding(.bottom, 12)
                    Divider()
                    ForEach(entries) { entry in
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            PlayerName(player: entry.player)
                                .fixedSize(horizontal: false, vertical: true)
                                .frame(minWidth: 0, maxWidth: .infinity, alignment: .leading)
                            Text(entry.correctPlayoff.map(String.init) ?? "—")
                                .frame(minWidth: 0, maxWidth: .infinity, alignment: .trailing)
                            Text(entry.correctUnknownPlayoff.map(String.init) ?? "—")
                                .frame(minWidth: 0, maxWidth: .infinity, alignment: .trailing)
                        }.font(.subheadline).monospacedDigit().padding(.vertical, 12)
                            .accessibilityElement(children: .contain)
                            .accessibilityLabel("\(entry.player.groupDisplayName), \(entry.correctPlayoff.map(String.init) ?? "unavailable") correct playoff games, \(entry.correctUnknownPlayoff.map(String.init) ?? "unavailable") correct unknown playoff games, all time")
                        if entry.id != entries.last?.id { Divider() }
                    }
                }.padding(14)
                    .frame(maxWidth: .infinity)
                    .background(Theme.card, in: RoundedRectangle(cornerRadius: 18))
                    .accessibilityIdentifier("playoffStandings")
            }
        }
    }

    private func heading(_ title: String, column: SortColumn, alignment: Alignment) -> some View {
        Button {
            if sortColumn == column { ascending.toggle() }
            else { sortColumn = column; ascending = column == .user }
        } label: {
            HStack(alignment: .top, spacing: 3) {
                Text(title).fixedSize(horizontal: false, vertical: true)
                if sortColumn == column {
                    Image(systemName: ascending ? "arrow.up" : "arrow.down")
                        .font(.system(size: 9, weight: .bold)).padding(.top, 3)
                }
            }
            .multilineTextAlignment(column == .user ? .leading : .trailing)
            .frame(minWidth: 0, maxWidth: .infinity, alignment: alignment)
            .frame(minHeight: 44, alignment: .top)
            .contentShape(Rectangle())
        }.buttonStyle(.plain).font(.caption.bold())
            .foregroundStyle(sortColumn == column ? Theme.orange : Color.secondary)
            .accessibilityLabel(title.replacingOccurrences(of: "\n", with: " "))
            .accessibilityValue(sortColumn == column ? (ascending ? "Sorted ascending" : "Sorted descending") : "Not sorted")
            .accessibilityHint("Double-tap to change the sort order")
    }
}

private struct PlayoffGameCard: View {
    let game: BowlGame
    let player: String?

    var body: some View {
        Card {
            HStack {
                Text(game.gameStatus).font(.caption2.bold()).foregroundStyle(Theme.orange)
                Spacer()
                Image(systemName: "chevron.right").font(.caption.bold()).foregroundStyle(.secondary)
            }
            Text(game.name).font(.subheadline.bold())
            team(game.awayTeam, score: game.awayScore)
            Divider()
            team(game.homeTeam, score: game.homeScore)
            Text(game.kickoffText).font(.caption).foregroundStyle(.secondary)
            Label(game.verificationLabel(), systemImage: game.verificationStatus() == "verified" ? "checkmark.square" : "square")
                .font(.caption).foregroundStyle(.secondary)
            if let player {
                Divider()
                let pick = game.picks[player]
                Text("Pick: \(pick ?? "No pick")").font(.caption.bold())
                if let pick, !pick.isEmpty, game.isFinal {
                    Label(pick == game.winner ? "Correct" : "Incorrect", systemImage: pick == game.winner ? "checkmark" : "xmark")
                        .font(.caption).foregroundStyle(pick == game.winner ? Color.green : Color.red)
                }
            }
        }
    }

    private func team(_ name: String, score: Int?) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(name).font(.subheadline).fontWeight(player.map { game.picks[$0] == name } == true ? .bold : .regular)
            if game.isFinal && game.winner == name {
                Image(systemName: "checkmark").accessibilityLabel("Winner")
            }
            Spacer()
            Text(score.map(String.init) ?? "—").font(.headline.monospacedDigit())
        }.foregroundStyle(game.isFinal && game.winner == name ? Color.green : Color.primary)
            .padding(.bottom, 5)
            .overlay(alignment: .bottom) {
                if let player, game.picks[player] == name { PickResultLine(outcome: game.pickOutcome(for: player)) }
            }
    }
}

struct GameDetailView: View {
    @EnvironmentObject private var store: AppStore
    let game: BowlGame
    private var players: [String] { store.snapshot?.players ?? [] }
    @State private var selected: Set<String> = []

    var body: some View {
        let game = store.snapshot?.games.first { $0.id == self.game.id } ?? self.game
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                GameCard(game: game, viewer: store.snapshot?.personalizedPlayer)
                if let checks = game.fieldVerification {
                    Card {
                        Text("Compare with original entries").font(.headline)
                        Text("Game verification checks kickoff and both opponents against unlive_games. Score verification checks both scores and their absolute difference against scores.")
                            .font(.caption).foregroundStyle(.secondary)
                        ForEach(BowlGame.checkedFields, id: \.key) { field in
                            if let check = checks[field.key] {
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack(alignment: .firstTextBaseline) {
                                        Text(field.label).font(.subheadline.weight(.semibold))
                                        Spacer()
                                    }
                                    Text("Live: \(check.value)").font(.subheadline)
                                    Text("\(check.source): \(check.originalValue)")
                                        .font(.caption).foregroundStyle(.secondary)
                                    TimelineView(.periodic(from: .now, by: 30)) { context in
                                        if check.currentStatus(at: context.date) != "verified" {
                                            Text(check.currentStatus(at: context.date) == "unavailable"
                                                ? "Not verified: invalid, unavailable or outdated data." : check.reason)
                                                .font(.caption).foregroundStyle(.secondary)
                                        }
                                    }
                                }
                                if field.key != BowlGame.checkedFields.last?.key { Divider() }
                            }
                        }
                    }
                }
                if !game.venue.isEmpty {
                    HStack {
                        Label(game.venue, systemImage: "mappin.and.ellipse")
                    }.font(.subheadline).foregroundStyle(.secondary)
                }
                if let url = game.espnURL {
                    HStack {
                        Link(destination: url) { Label("Open ESPN Gamecast", systemImage: "arrow.up.right.square") }
                            .buttonStyle(.bordered)
                    }
                }
                HStack {
                    SectionHeading(title: "Everyone’s picks")
                    PlayerFilter(players: players, selected: $selected)
                }
                Card {
                    if selected.isEmpty { Text("Choose players to see their picks.").foregroundStyle(.secondary) }
                    ForEach(players.filter { selected.contains($0) }, id: \.self) { player in
                        HStack {
                            PlayerAvatar(player: player)
                            PlayerName(player: player).font(.subheadline)
                            Spacer(minLength: 10)
                            VStack(alignment: .trailing, spacing: 3) {
                                Text(game.picks[player] ?? "No pick").font(.subheadline.weight(.semibold)).multilineTextAlignment(.trailing)
                                if game.isFinal, let pick = game.picks[player] {
                                    HStack {
                                        Label(pick == game.winner ? "Correct" : "Incorrect",
                                              systemImage: pick == game.winner ? "checkmark.circle.fill" : "xmark.circle")
                                            .font(.caption).foregroundStyle(pick == game.winner ? .green : .red)
                                    }
                                }
                            }
                        }
                        if player != players.filter({ selected.contains($0) }).last { Divider() }
                    }
                }
            }.padding(20)
        }.background(Theme.background).navigationTitle("Game details").navigationBarTitleDisplayMode(.inline)
            .onAppear { selected = Set(players) }
            .onChange(of: players) { old, players in
                selected = selected == Set(old) ? Set(players) : selected.intersection(players)
            }
    }
}

struct StandingsView: View {
    @EnvironmentObject private var store: AppStore
    @State private var margin = false
    var body: some View {
        if let data = store.snapshot {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    SectionHeading(title: "The race for the chalice", caption: "\(data.players.count) players · \(data.completed) of \(data.games.count) games complete")
                    Picker("Leaderboard", selection: $margin) {
                        Text("Correct picks").tag(false)
                        Text("Point difference").tag(true)
                    }.pickerStyle(.segmented)
                    Card {
                        let ranked = data.ranked(by: margin)
                        ForEach(Array(ranked.enumerated()), id: \.element.id) { index, entry in
                            let value = margin ? entry.pointDifference : entry.overallScore
                            let rank = 1 + ranked.filter { (margin ? $0.pointDifference : $0.overallScore) > value }.count
                            HStack(spacing: 12) {
                                Text(String(rank)).font(.headline.monospacedDigit()).foregroundStyle(rank == 1 ? Theme.orange : .secondary).frame(minWidth: 20)
                                PlayerAvatar(player: entry.player)
                                VStack(alignment: .leading, spacing: 4) {
                                    PlayerName(player: entry.player).font(.headline)
                                    Text(margin ? "\(entry.correct) correct picks" : "Correct picks")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer(minLength: 4)
                                if margin {
                                    Text(value.scoreText).font(.title3.bold().monospacedDigit())
                                        .lineLimit(1).minimumScaleFactor(0.65)
                                } else {
                                    StandingScore(standing: entry)
                                }
                            }.padding(.vertical, 5)
                            if index < ranked.count - 1 { Divider() }
                        }
                    }
                    Text(margin ? "Points gained in wins, minus points lost in losses, for each player’s picks." : "Correct picks are the official score. The smaller value in parentheses is the MBCC score from the spreadsheet.")
                        .font(.footnote).foregroundStyle(.secondary)
                    updatedLabel(data)
                }.padding(20)
            }.refreshable { await store.refresh() }
        }
    }
}

struct SeasonView: View {
    @EnvironmentObject private var store: AppStore
    @State private var selected: Set<String> = []
    @State private var margin = false
    @State private var player = ""
    @State private var matrix = false

    var body: some View {
        if let data = store.snapshot {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    HStack {
                        SectionHeading(title: "How the season unfolds")
                        PlayerFilter(players: data.players, selected: $selected)
                    }
                    Card {
                        SectionHeading(title: "Correct picks")
                        if selected.isEmpty { Text("Choose players to see the charts.").foregroundStyle(.secondary) }
                        else {
                            CorrectPicksChart(standings: data.standings.filter { selected.contains($0.player) }, viewer: data.personalizedPlayer)
                        }
                    }
                    Picker("Progress metric", selection: $margin) {
                        Text("Correct picks").tag(false)
                        Text("Point chaos").tag(true)
                    }.pickerStyle(.segmented)
                    Card {
                        SectionHeading(title: margin ? "Point Chaos Argyle" : "Argyle chart", caption: "Progress after each completed game")
                        if data.progress.isEmpty { Text("Charts appear after the first result.").foregroundStyle(.secondary) }
                        else {
                            Chart {
                                ForEach(data.players.filter { selected.contains($0) }, id: \.self) { player in
                                    ForEach(data.progress) { point in
                                        if let value = (margin ? point.pointDifference : point.correct)[player] {
                                            LineMark(x: .value("Game", point.gameIndex), y: .value("Score", value))
                                                .foregroundStyle(by: .value("Player", player))
                                                .lineStyle(StrokeStyle(lineWidth: player == data.personalizedPlayer ? 4 : data.personalizedPlayer == nil ? 2.5 : 1.8))
                                                .accessibilityLabel(player.groupDisplayName)
                                        }
                                    }
                                }
                            }
                            .chartForegroundStyleScale(domain: data.players, range: Theme.playerColors)
                            .chartLegend {
                                LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), alignment: .leading)], alignment: .leading) {
                                    ForEach(Array(data.players.enumerated()), id: \.element) { index, name in
                                        if selected.contains(name) {
                                            HStack(spacing: 5) {
                                                Circle().fill(Theme.playerColors[index % Theme.playerColors.count])
                                                    .frame(width: 8, height: 8)
                                                PlayerName(player: name).font(.caption)
                                            }
                                        }
                                    }
                                }
                            }
                            .chartXAxisLabel("Games completed")
                            .frame(height: 300)
                        }
                    }
                    SectionHeading(title: "Elimination check", caption: "Who can still reach the top?")
                    Card {
                        Picker("Player", selection: $player) {
                            ForEach(data.players, id: \.self) { PlayerName(player: $0).tag($0) }
                        }.pickerStyle(.menu)
                        if !player.isEmpty {
                            let result = data.elimination(for: player)
                            Label(result.eliminated ? "Eliminated" : "Not yet eliminated",
                                  systemImage: result.eliminated ? "xmark.circle" : "checkmark.seal.fill")
                                .font(.title3.bold()).foregroundStyle(result.eliminated ? Color.secondary : Color.green)
                            Text("\(result.best) correct picks in \(player.groupDisplayName)’s best case").font(.subheadline)
                            ForEach(result.comparisons) { comparison in
                                HStack {
                                    PlayerName(player: comparison.player)
                                    Spacer()
                                    Text(String(comparison.correct)).monospacedDigit()
                                }.font(.subheadline).foregroundStyle(comparison.player == player ? .primary : .secondary)
                            }
                            Text("Assumes this player wins every remaining possible pick, then compares the shared picks others would also win. Ties remain alive. Like the original app, this check does not solve every possible playoff bracket.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    DisclosureGroup("Full elimination matrix", isExpanded: $matrix) {
                        ScrollView(.horizontal) {
                            Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 12) {
                                GridRow {
                                    Text("Best case for ↓").font(.caption.bold())
                                    ForEach(data.players, id: \.self) { PlayerName(player: $0).font(.caption) }
                                }
                                ForEach(data.players, id: \.self) { candidate in
                                    GridRow {
                                        PlayerName(player: candidate).font(.caption)
                                        ForEach(data.elimination(for: candidate).comparisons) { item in
                                            Text(String(item.correct)).font(.caption.monospacedDigit())
                                        }
                                    }
                                }
                            }.padding(.vertical, 12)
                        }
                    }.font(.subheadline.weight(.medium))
                }.padding(20)
            }.refreshable { await store.refresh() }
                .onAppear { if player.isEmpty { reset(data) } }
                .onChange(of: data.players) { _, _ in reset(data) }
        }
    }

    private func reset(_ data: Snapshot) { selected = Set(data.players); player = data.players.first ?? "" }
}

struct HistoryView: View {
    @EnvironmentObject private var store: AppStore
    @State private var player = "All Players"
    @State private var moreThanWinners = false

    var body: some View {
        if let data = store.snapshot {
            let players = Array(Set(data.history.map(\.player) + data.careers.map(\.player))).sorted()
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    SectionHeading(title: "A tradition worth keeping", caption: "Mehfoud Bowl Challenge Chalice")
                    Card {
                        Picker("Player", selection: $player) {
                            Text("All Players").tag("All Players")
                            ForEach(players, id: \.self) { PlayerName(player: $0).tag($0) }
                        }
                        Toggle("Show more than winners", isOn: $moreThanWinners)
                    }.font(.subheadline)
                    SectionHeading(title: "Player season breakdown")
                    let entries = data.history.filter {
                        (moreThanWinners || $0.isWinner)
                            && (player == "All Players" || player == $0.player)
                    }.sorted { $0.season > $1.season }
                    if entries.isEmpty { EmptyCard(title: "No matching results", message: "Try changing the player filter in Data Connection or showing more than winners.") }
                    // A workbook can have multiple rows for the same player/season.
                    // Preserve each source row rather than reusing its compound ID.
                    ForEach(Array(entries.enumerated()), id: \.offset) { _, entry in
                        Card {
                            HStack {
                                Label(entry.season.groupDisplayName, systemImage: entry.isWinner ? "trophy.fill" : "calendar")
                                    .font(.caption.bold()).foregroundStyle(Theme.orange)
                                Spacer()
                                Text(entry.award).font(.caption).foregroundStyle(.secondary)
                            }
                            HStack {
                                PlayerName(player: entry.player).font(.title3)
                                Spacer()
                                Text(entry.percentage.percentText).font(.title3.bold().monospacedDigit())
                            }
                            Text("\(entry.correct) correct of \(entry.games) picks").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    SectionHeading(title: "Player career breakdown")
                    Card {
                        ForEach(data.careers.filter { player == "All Players" || player == $0.player }) { career in
                            HStack {
                                PlayerName(player: career.player).font(.subheadline)
                                Spacer()
                                VStack(alignment: .trailing, spacing: 3) {
                                    Text(career.percentage.percentText).font(.headline.monospacedDigit())
                                    Text("\(career.wins) W · \(career.losses) L").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    SectionHeading(title: "MBCC season breakdown")
                    Card {
                        ForEach(data.seasons.sorted { $0.season > $1.season }) { season in
                            HStack {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(season.season.groupDisplayName).font(.subheadline.bold())
                                    Text("\(season.wins) W · \(season.losses) L").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(season.percentage.percentText).font(.headline.monospacedDigit())
                            }
                        }
                    }
                }.padding(20)
            }.refreshable { await store.refresh() }
                .onChange(of: players) { _, players in
                    if player != "All Players" && !players.contains(player) { player = "All Players" }
                }
        }
    }
}

struct TodaysUpdateView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 28) {
                let posts = store.snapshot?.updatePosts ?? []
                if posts.isEmpty {
                    ContentUnavailableView("No update yet", systemImage: "megaphone",
                        description: Text("Check back here for the latest MBCC news and videos."))
                } else {
                    ForEach(Array(posts.enumerated()), id: \.offset) { index, update in
                        if index == 1 {
                            SectionHeading(title: "Previous updates")
                                .padding(.top, 8)
                        }
                        if index > 1 { Divider() }
                        UpdatePostView(update: update, isLatest: index == 0)
                    }
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(20)
        }
        .background(Theme.background)
        .navigationTitle("Today’s Update")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await store.refresh() }
    }
}

private struct UpdatePostView: View {
    let update: DailyUpdate
    let isLatest: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 10) {
                if isLatest {
                    Text("LATEST UPDATE").font(.caption.bold()).tracking(2)
                        .foregroundStyle(Theme.orange)
                }
                Label(update.dateLabel, systemImage: "calendar")
                    .font(.subheadline).foregroundStyle(Theme.orange)
                Text(update.title).font(isLatest ? .largeTitle.bold() : .title2.bold())
                if !update.message.isEmpty {
                    Text(update.message).font(.body).textSelection(.enabled)
                }
            }
            if let video = update.video {
                Link(destination: video.url) {
                    VStack(alignment: .leading, spacing: 0) {
                        Color.clear.aspectRatio(16 / 9, contentMode: .fit)
                            .overlay {
                                AsyncImage(url: video.thumbnailURL) { phase in
                                    if let image = phase.image {
                                        image.resizable().scaledToFill()
                                    } else {
                                        Rectangle().fill(Theme.navy)
                                    }
                                }
                            }
                            .clipped()
                            .overlay {
                                Image(systemName: "play.fill").font(.title)
                                    .foregroundStyle(.white).padding(22)
                                    .background(.black.opacity(0.65), in: Circle())
                            }
                        HStack {
                            Label("Watch on YouTube", systemImage: "play.rectangle.fill")
                                .font(.headline)
                            Spacer()
                            Image(systemName: "arrow.up.right").font(.subheadline.bold())
                        }.padding(18)
                    }
                    .foregroundStyle(.primary)
                    .background(Theme.card, in: RoundedRectangle(cornerRadius: 22))
                    .clipShape(RoundedRectangle(cornerRadius: 22))
                }
                .accessibilityLabel("Watch \(update.title) on YouTube")
                .accessibilityHint("Opens YouTube or your browser")
                .accessibilityIdentifier("updateVideo")
                Text("Opens in YouTube or your browser.")
                    .font(.caption).foregroundStyle(.secondary)
            } else if update.youtubeURL?.isEmpty == false {
                Label("The video is unavailable right now. Check back soon.", systemImage: "video.slash")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct InformationView: View {
    @EnvironmentObject private var store: AppStore
    private let tiebreakers = ["Point spread", "Correct upset picks", "Correct playoff bracket picks", "Potential upset picks attempted", "Point spread of correct upset picks", "Point spread of playoff bracket picks", "Point spread of all attempted upset picks", "MBCC commemorative coin flip"]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Card {
                    Image(systemName: "trophy.fill").font(.largeTitle).foregroundStyle(Theme.orange)
                    SectionHeading(title: "One chalice. All the bragging rights.")
                    Text("Pick the most games correctly to win. Root for your teams to win big—or lose by as little as possible—to build your point difference.")
                }
                SectionHeading(title: "Tiebreakers", caption: "In order, to decide first versus second")
                Card {
                    ForEach(Array(tiebreakers.enumerated()), id: \.offset) { index, rule in
                        HStack(alignment: .top, spacing: 12) {
                            Text(String(index + 1)).font(.subheadline.bold()).foregroundStyle(Theme.orange).frame(width: 18)
                            Text(rule).font(.subheadline)
                        }
                    }
                }
                SectionHeading(title: "The winnings", caption: "Rules from the 2025–26 Streamlit app")
                Card {
                    prize("First place", amount: "$300", detail: "Most correct picks, tiebreakers if needed, and a name on the trophy.")
                    Divider()
                    prize("Second place", amount: "~$150", detail: "Best point difference; prize is whatever is in the change jar.")
                    Divider()
                    prize("Hokie Prize", amount: "$300", detail: "Split between those who beat Papa Smurf’s number of wins.")
                }
                if let data = store.snapshot {
                    Card {
                        SectionHeading(title: "The trophy cabinet", caption: store.currentPlayersOnly ? "Current players" : "Every player, past and present")
                        let records = data.championships
                        ForEach(Array(records.enumerated()), id: \.element.id) { index, record in
                            ChampionshipRow(record: record)
                            if index < records.count - 1 { Divider() }
                        }
                        Text("Half trophies mark shared championships. Nicholas and Joseph shared the first MBCC.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                Card {
                    SectionHeading(title: "About the data")
                    Text(store.isSampleData ? "You’re exploring fictional sample results. Connect the MBCC spreadsheet backend in Data Connection for real results." : "The app refreshes every minute while open. When enabled, live_scores_and_games supplies game details, scores and winners. Each field is compared with its original spreadsheet entry. Standings and history use their existing summary tabs.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    if let data = store.snapshot { updatedLabel(data) }
                    Text("All dates and times use Eastern Time (ET).").font(.caption).foregroundStyle(.secondary)
                }
            }.padding(20)
        }.background(Theme.background)
    }

    private func prize(_ title: String, amount: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack { Text(title).font(.headline); Spacer(); Text(amount).font(.title3.bold()).foregroundStyle(Theme.orange) }
            Text(detail).font(.subheadline).foregroundStyle(.secondary)
        }
    }
}

struct ConnectionView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var demo = true
    @State private var endpoint = ""
    @State private var keyword = ""
    @FocusState private var focusedField: ConnectionField?
    private enum ConnectionField { case keyword, endpoint }
    private var validEndpoint: Bool { demo || AppStore.validURL(endpoint.trimmingCharacters(in: .whitespacesAndNewlines)) != nil }
    private var valid: Bool { validEndpoint }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SecureField("Enter keyword", text: $keyword)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .focused($focusedField, equals: .keyword).submitLabel(.done)
                        .onSubmit { focusedField = nil }.accessibilityIdentifier("groupKeyword")
                } header: {
                    Text("Keyword")
                } footer: {
                    Text("Applies to every tab and game details.")
                }
                Section {
                    Toggle("Current players only", isOn: $store.currentPlayersOnly)
                        .accessibilityIdentifier("currentPlayersOnly")
                } header: {
                    Text("Player filters")
                } footer: {
                    Text("Applies immediately to every tab and game details. Turn off to include former players.")
                }
                Section {
                    Toggle("Explore demo data", isOn: $demo)
                } footer: {
                    Text("Demo scores and history are fictional. Turn this off to connect to your real MBCC data.")
                }
                Section {
                    TextField("https://your-server.com/api/snapshot", text: $endpoint)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                        .focused($focusedField, equals: .endpoint).submitLabel(.done)
                        .onSubmit { focusedField = nil }
                        .accessibilityIdentifier("snapshotURL")
                    if !validEndpoint { Text("Enter a full HTTPS URL.").font(.caption).foregroundStyle(.red) }
                } header: {
                    Text("MBCC snapshot URL")
                } footer: {
                    Text("Use the read-only backend included with this project. Google credentials stay on your server.")
                }
                Section {
                    Button("Save connection") {
                        let useDemo = demo, url = endpoint, groupKeyword = keyword
                        dismiss()
                        Task { await store.configure(demo: useDemo, endpoint: url, keyword: groupKeyword) }
                    }.disabled(!valid).accessibilityIdentifier("saveConnection")
                }
            }.navigationTitle("Data Connection").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
                .onAppear { demo = store.isDemo; endpoint = store.endpoint; keyword = store.groupKeyword }
        }
    }
}

private func updatedLabel(_ data: Snapshot) -> some View {
    let date = ISO8601DateFormatter().date(from: data.updatedAt)
    return Text(date.map { "Updated \(EasternTime.text($0))" } ?? "Update time unavailable")
        .font(.caption).foregroundStyle(.secondary)
}

private struct CorrectPicksChart: View {
    let standings: [Standing]
    let viewer: String?
    var body: some View {
        Chart(standings) { entry in
            BarMark(x: .value("Correct", entry.correct), y: .value("Player", entry.player))
                .foregroundStyle(Theme.orange)
                .annotation(position: .trailing) {
                    if entry.player == viewer { Text(entry.correct, format: .number).font(.caption.bold()) }
                }
                .accessibilityLabel(entry.player.groupDisplayName)
        }
        .chartYAxis {
            AxisMarks { value in
                AxisValueLabel {
                    if let name = value.as(String.self) {
                        PlayerName(player: name).fontWeight(name == viewer ? .bold : .regular)
                    }
                }
            }
        }
        .frame(height: CGFloat(max(standings.count, 1) * 30 + 30))
    }
}

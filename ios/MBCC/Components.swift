import SwiftUI

enum Theme {
    static let orange = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 1, green: 0.64, blue: 0.34, alpha: 1)
        : UIColor(red: 0.65, green: 0.25, blue: 0.07, alpha: 1) })
    static let navy = Color(red: 0.08, green: 0.14, blue: 0.20)
    static let background = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark
        ? .systemGroupedBackground : UIColor(red: 0.97, green: 0.96, blue: 0.94, alpha: 1) })
    static let card = Color(uiColor: .secondarySystemGroupedBackground)
    static let playerColors: [Color] = [.blue, .orange, .green, .purple, .pink, .teal, .indigo, .brown, .red, .cyan]
}

struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 16) { content }
            .padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.card, in: RoundedRectangle(cornerRadius: 22))
    }
}

struct SectionHeading: View {
    let title: String
    var caption: String? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.title3.bold())
            if let caption { Text(caption).font(.subheadline).foregroundStyle(.secondary) }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct PlayerAvatar: View {
    let player: String
    var body: some View {
        Text(String(player.prefix(1))).font(.subheadline.bold())
            .frame(width: 36, height: 36)
            .foregroundStyle(Theme.orange)
            .background(Theme.orange.opacity(0.1), in: Circle())
            .accessibilityHidden(true)
    }
}

struct PlayerName: View {
    @EnvironmentObject private var store: AppStore
    let player: String
    var baseline: Font.Weight = .semibold

    private var viewer: String? { store.snapshot?.personalizedPlayer }
    private var isPersonal: Bool { viewer == player }

    var body: some View {
        Text(player.groupDisplayName)
            .fontWeight(viewer == nil ? baseline : isPersonal ? .bold : .regular)
            .accessibilityIdentifier(isPersonal ? "personalizedPlayerName" : "playerName")
    }
}

struct StandingScore: View {
    let standing: Standing
    var font: Font = .title3

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 5) {
            Text(String(standing.correct)).font(font.bold())
            Text("(\(standing.overallScore.scoreText))")
                .font(.caption).foregroundStyle(.secondary)
        }
        .monospacedDigit()
        .lineLimit(1)
        .minimumScaleFactor(0.65)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(standing.correct) correct picks, MBCC score \(standing.overallScore.scoreText)")
    }
}

struct ChampionshipRow: View {
    let record: ChampionshipRecord

    var body: some View {
        HStack(spacing: 12) {
            PlayerName(player: record.player).font(.headline)
            Spacer(minLength: 8)
            HStack(spacing: 4) {
                ForEach(0..<record.fullWins, id: \.self) { _ in trophy }
                ForEach(0..<record.sharedWins, id: \.self) { _ in
                    trophy.mask(alignment: .leading) {
                        Rectangle().frame(width: 11)
                    }
                }
            }.accessibilityHidden(true)
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(record.player.groupDisplayName), \(record.fullWins) outright championships, \(record.sharedWins) shared championships, \(record.trophyCount.scoreText) trophies")
    }

    private var trophy: some View {
        Image(systemName: "trophy.fill")
            .font(.system(size: 20)).foregroundStyle(Theme.orange)
            .frame(width: 22, height: 26)
    }
}

struct EmptyCard: View {
    let title: String
    let message: String
    var body: some View {
        ContentUnavailableView(title, systemImage: "sportscourt", description: Text(message))
            .frame(maxWidth: .infinity).padding(.vertical, 24)
    }
}

private struct PickRuleShape: Shape {
    func path(in rect: CGRect) -> Path {
        Path { path in
            path.move(to: CGPoint(x: 0, y: rect.midY))
            path.addLine(to: CGPoint(x: rect.maxX, y: rect.midY))
        }
    }
}

struct PickResultLine: View {
    let outcome: PickOutcome?
    var body: some View {
        if outcome == .correct {
            Rectangle().fill(Color.green).frame(height: 2).accessibilityHidden(true)
        } else if outcome == .incorrect {
            PickRuleShape().stroke(Color.gray, style: StrokeStyle(lineWidth: 2, lineCap: .round, dash: [1, 4]))
                .frame(height: 2).accessibilityHidden(true)
        }
    }
}

struct GameCard: View {
    let game: BowlGame
    var viewer: String? = nil
    var body: some View {
        Card {
            HStack(alignment: .firstTextBaseline) {
                Text(game.name).font(.subheadline.bold())
                Spacer(minLength: 8)
                Text(game.gameStatus)
                    .font(.caption2.bold()).foregroundStyle(game.live?.status == "live" ? Theme.orange : .secondary)
            }
            VStack(spacing: 12) {
                teamRow(game.awayTeam, score: game.displayedAwayScore)
                teamRow(game.homeTeam, score: game.displayedHomeScore)
            }
            if let viewer, let pick = game.picks[viewer], !pick.isEmpty,
               pick != game.homeTeam && pick != game.awayTeam {
                Text("Your pick: \(pick)").font(.subheadline.bold()).padding(.bottom, 5)
                    .overlay(alignment: .bottom) { PickResultLine(outcome: game.pickOutcome(for: viewer)) }
            }
            if let difference = game.pointDifference {
                Text("Score difference: \(difference)").font(.caption).foregroundStyle(.secondary)
            }
            GameVerificationMark(game: game, forGame: false)
            if let date = game.live?.fetchedDate {
                HStack(spacing: 4) {
                    Text("\(game.live?.source ?? "Live") updated")
                    Text(date, style: .relative)
                    Text("ago")
                }.font(.caption2).foregroundStyle(.secondary)
            }
            HStack {
                Label(game.kickoffText, systemImage: "clock")
                Spacer()
                Text(game.network)
            }.font(.caption).foregroundStyle(.secondary)
            GameVerificationMark(game: game, forGame: true)
            if game.upset == true {
                HStack {
                    Label("Upset pick game", systemImage: "bolt.fill")
                }.font(.caption.weight(.medium)).foregroundStyle(.blue)
            }
            if game.unanimous == true {
                HStack {
                    Label("Unanimous pick", systemImage: "person.3.fill")
                }.font(.caption.weight(.medium)).foregroundStyle(.secondary)
            }
            if let focus = game.focusTeam {
                HStack {
                    Text("Focus: \(focus)")
                }.font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func teamRow(_ team: String, score: Int?) -> some View {
        let selected = viewer.flatMap { game.picks[$0] } == team
        return HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 3).fill(game.winner == team ? Color.green : Theme.navy.opacity(0.25))
                .frame(width: 4, height: 22)
            Text(team).font(.headline).fontWeight(viewer == nil ? .semibold : selected ? .bold : .regular)
                .accessibilityLabel(viewer.map { game.picks[$0] == team ? "\(team), your pick, \(game.pickOutcome(for: $0)?.rawValue ?? "pending")" : team } ?? team)
            if game.winner == team {
                Image(systemName: "trophy.fill").foregroundStyle(.green).accessibilityLabel("Winner")
            }
            Spacer()
            Text(score.map(String.init) ?? "—").font(.title2.bold().monospacedDigit())
        }
        .foregroundStyle(game.focusTeam == team && game.upset == true ? Color.blue : .primary)
        .padding(.bottom, 5)
        .overlay(alignment: .bottom) {
            if let viewer, game.picks[viewer] == team { PickResultLine(outcome: game.pickOutcome(for: viewer)) }
        }
    }
}

struct GameVerificationMark: View {
    let game: BowlGame
    let forGame: Bool
    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let status = game.verificationStatus(at: context.date, forGame: forGame)
            Label(game.verificationLabel(at: context.date, forGame: forGame),
                  systemImage: status == "verified" ? "checkmark.square.fill" : "square")
                .font(.caption.weight(.medium))
                .foregroundStyle(status == "verified" ? Color.green : status == "mismatch" ? Color.red : Color.secondary)
                .accessibilityIdentifier(forGame ? "gameVerification" : "scoreVerification")
        }
    }
}

struct PlayerFilter: View {
    let players: [String]
    @Binding var selected: Set<String>
    var body: some View {
        Menu {
            Button("Show all") { selected = Set(players) }
            ForEach(players, id: \.self) { player in
                Button {
                    if selected.contains(player) { selected.remove(player) } else { selected.insert(player) }
                } label: {
                    Label {
                        PlayerName(player: player)
                    } icon: {
                        Image(systemName: selected.contains(player) ? "checkmark.circle.fill" : "circle")
                    }
                }
            }
        } label: {
            Label("Players (\(selected.count))", systemImage: "line.3.horizontal.decrease")
                .font(.subheadline.weight(.medium))
        }.accessibilityIdentifier("playerFilter")
    }
}

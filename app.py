import streamlit as st
import pandas as pd
import pandasql as ps
#from google.oauth2 import service_account
import numpy as np
import matplotlib.pyplot as plt
import plotly.figure_factory as ff
import plotly.express as px
import plotly.graph_objs as go
from live_results_scrape import get_schedule
from toggles import toggle_list
from highlighting_nightmare import highlight_all_names, highlight_all_games
from people_list import people_list
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression
import datetime
import streamlit as st
#from google.oauth2 import service_account
#from shillelagh.backends.apsw.db import connect
from streamlit_gsheets import GSheetsConnection
from PIL import Image

st.set_page_config(layout="wide")

st.header ("""
MBCC 13 in 2024-25
""")

#pick_url = 'https://forms.gle/W8HCNsmgwr1oWYoR6'
#st.header("Make your [picks](%s) before this Friday the 13th at 13:00!" % pick_url)
#st.header("'twas the night before bowl season...")
#st.header("Day 1 - Best Day of the Year! Maybe?")
#st.header("Day 2 - Almost Heaven?")
#st.header("Day 3 - Double Header and a chance for Nemo, Gregory, and Emma to pull back into the group and Elise to take the lead!")
#st.header("Day 4 - A new chance at first place?")
#st.header("Day 5 - New best Day of the year! Playoffs!?!")
#st.header("Day 6 - Shake up at the top of the MBCC and the quarterfinals decided tonight!")
#st.header("Day 7 - Another 1st place shake up!")
#st.header("Day 8 - Christmas Eve Tradition")
#st.header("Day 9 - The ramp up begins!")
#st.header("Day 10 - Taking down the Christmas Tree")
#st.header("Day 11 - Official best day of the year!")
#st.header("Day 14 - Playoffs Continue!")
#st.header("Day 15 - Let's Go Hokies!")
#st.header("Day 17 & 18 - Semifinals - for MBCC and the CFP!")
st.header("Day 19 - CFP Final & MBCC Decided")
#st.header("The Picks are IN! - HERE WE GO!")
#st.header("Day 1 - 7 games - Upset Pick City!")
#st.header("Day 2 - What a comeback win to cut the first place cluster down to two!")
#st.header("Day 3 - Is Papa Smurf bringing Emma down?")
#st.header("Day 4 - When it rains, it pours... even on roofs, even if for a short time. It's still early.")
#st.header("Day 5 - Florida again?! Georgia Tech and Gregory say NOPE!")
#st.header("Day 6 - A lotta Bowls Bonanza in Alabama - big night for Nemo?!")
#st.header("Day 7 - Room for improvement - throw away those old, worn-out, bad picks and get those shiny, freshly unwrapped, new picks some sun!")
#st.header("Day 8 - Go Hokies!")
#st.header("Day 9 - Then there were Nine - cuz like, day 9 and 9 people left?")
#st.header("Day 10 - The first place curse strikes again")
#st.header("Day 11 - The points race is heating up, you want your pick to win BIG")
#st.header("Day 12 - The Hokie Prize is still in reach for everyone!")
#st.header("Day 13 - Christopher takes the Crown before the Championship, but there's still a reason to watch!")
#st.header("MBCC 12 Champion - Christopher; MBCC 12 Second Place - Joseph")
st.header("LET THE PLAYOFFS END!")

##TODO drop down here for players (create player tab?)
## set option to have current winner in bold

# Create a connection object.
# credentials = service_account.Credentials.from_service_account_info(
#     st.secrets["gcp_service_account"],
#     scopes=[
#         "https://www.googleapis.com/auth/spreadsheets",
#     ],
# )
conn = st.connection("gsheets", type=GSheetsConnection)

st.cache_data(ttl="603m")
def run_query_history(worksheet_name):
    df = conn.read(worksheet=worksheet_name)
    return df


st.cache_data(ttl="240s")
def run_query_current_1(worksheet_name):
    df = conn.read(worksheet=worksheet_name)
    return df


st.cache_data(ttl="300s")
def run_query_current_2(worksheet_name):
    df = conn.read(worksheet=worksheet_name)
    return df


st.cache_data(ttl="60m")
def run_query_delayed(worksheet_name):
    df = conn.read(worksheet=worksheet_name)
    return df


### change this in december!!! old code to pull in data from ESPN directly, they change their json html too often
# st.cache_data(ttl=60)
# def bring_in_live_games():
#     return get_schedule()


#current_scores = st.secrets["current_pick_success"]
current_scores = run_query_current_1("current_pick_success")
#history_sheet = st.secrets["history_sheet"]
history_sheet = run_query_history("basic_history")
#agg_history = st.secrets["agg_history"]
agg_history = run_query_history("agg_history")
#season_history = st.secrets["season_history"]
season_history = run_query_history("season_history")
#picks = st.secrets["picks"]
picks = run_query_delayed("picks")
#unlive_games = st.secrets["unlive_games"]
unlive_games = run_query_delayed("unlive_games")
#live_tracker_binary = st.secrets["live_tracker_binary"]
live_tracker_binary = run_query_current_2("live_tracker_binary")
#live_tracker_complex = st.secrets["live_tracker_complex"]
live_tracker_complex = run_query_current_2("live_tracker_complex")
#unlive_scores = st.secrets["tournament_scores"]
unlive_scores = run_query_current_1("scores")
#full_score_matrix = st.secrets["full_pick_summary"]


starting_people_list = people_list()
the_people_list = people_list()
#current_scores_df = pd.DataFrame(run_query(f'SELECT * FROM "{current_scores}"'))
current_scores_df = current_scores

games_in = current_scores_df.iloc[4]['Christopher']
games_left = current_scores_df.iloc[5]['Christopher']

games_in_s = str(int(games_in))
games_left_s = str(int(games_left))


### creation of the columns
col1,col2 = st.columns(2)

#main score
main_score_df = current_scores_df[(current_scores_df["Situation"]=="mbcc_score") | (current_scores_df["Situation"]=="Correct")].T.rename_axis('Situation').reset_index()
main_score_df = main_score_df[1:]
main_score_df.columns = ["Player", "Picks Correct", "Overall Score"]

main_score_df["Overall Rank"] = main_score_df["Overall Score"].rank(ascending = False)
main_score_df = main_score_df.sort_values(by=["Overall Rank"])

#point difference score
point_diff_score_df = current_scores_df[current_scores_df["Situation"]=="point_difference"].T.rename_axis('Situation').reset_index()
point_diff_score_df = point_diff_score_df[1:]
point_diff_score_df.columns = ["Player", "Point Difference"]

point_diff_score_df["Point Difference Rank"] = point_diff_score_df["Point Difference"].rank(ascending = False)
point_diff_score_df = point_diff_score_df.sort_values(by=["Point Difference Rank"])

with col1:
	st.header("Overall Score")
	st.dataframe(main_score_df, hide_index=True)

with col2:
	st.header("Point Difference Score")
	st.dataframe(point_diff_score_df, hide_index=True)


st.write("We are currently ", games_in_s, " games in, which means we have ", games_left_s, " games left. We've completed ", str(round(100*games_in/(games_in+games_left),2)), "% of MBCC13.")
### creation of the tabs
#tab_today, tab_mbcc_12, tab_elimination, tab_history, sql_learning = st.tabs(["Live", "MBCC 12", "Elimination Check", "History", "Click Here Gregory"])
tab_today, tab_mbcc_13, tab_elimination, tab_history, need_to_know = st.tabs(["Live", "MBCC 13", "Elimination Check", "History", "Information"])

### set up the games to include a link and then scores from the scores page???
with tab_today:
	st.header("Games")
	#live_df = bring_in_live_games()
	#live_df = pd.DataFrame(run_query(f'SELECT * FROM "{unlive_games}"'))
	live_df = unlive_games
	unlive_games['game_date'] = pd.to_datetime(unlive_games['game_date']).dt.date
	unlive_games['game_time'] = pd.to_datetime(unlive_games['game_time'])
	
	live_df['game_page'] = "https://www.espn.com/college-football/game?gameId="+live_df['game_id'].astype(int).astype(str)
	live_df['time'] = live_df['game_time'].dt.strftime('%I:%M %p')
	
	#scores_df = pd.DataFrame(run_query(f'SELECT * FROM "{unlive_scores}"'))
	scores_df = unlive_scores
	scores_df = scores_df.fillna(0)

	new_live_df = live_df.merge(scores_df, left_on = "game_name", right_on = "game")
	new_live_df = new_live_df[['game_date', 'time', 'game_name', 'game_venue', 'game_network', 'game_home_team', 'game_away_team', 'home_team_score', 'away_team_score', 'winner', 'game_page', 'upset_indicator', 'unanimous_indicator', 'team_focus_indicator']]

	new_live_df['home_team_score'] = new_live_df['home_team_score'].astype(int)
	new_live_df['away_team_score'] = new_live_df['away_team_score'].astype(int)
	
	new_live_df['upset_indicator'] = np.where(new_live_df.upset_indicator == 1, True, False)
	new_live_df['unanimous_indicator'] = np.where(new_live_df.unanimous_indicator == 1, True, False)
	# adding time formatting for nemo... does nothing for the visuals and use of the app; but hey, Nemo might be happy?
	### this could be a bug with streamlit sorting dataframes??? 
	#new_live_df['time'] = pd.to_datetime(new_live_df['time']).dt.strftime('%H:%M')
	
	games_without_scores = scores_df[scores_df.winner == 'TBD']['game'].to_list()
	# bringing in picks
	#picks_df = pd.DataFrame(run_query(f'SELECT * FROM "{picks}"'))
	picks_df = picks
	picks_dates = picks_df.merge(new_live_df[["game_name", "game_date", "game_home_team", "game_away_team", "winner"]], left_on = "Game", right_on = "game_name")
	
	picks_dates["loser"] = np.where(picks_dates["winner"] == 'TBD', 'TBD', np.where(picks_dates["game_home_team"] == picks_dates["winner"], picks_dates["game_away_team"], picks_dates["game_home_team"]))

	actual_today = pd.to_datetime((datetime.datetime.today()-pd.Timedelta(hours=5)).strftime('%Y-%m-%d'))
	#st.write(actual_today)
	### today, future, all drop down to show picks
	option = st.selectbox("Select Games to See", ("Today", "Future", "All"))
	
	if option == "All":
		st.dataframe(new_live_df.style.apply(highlight_all_games, axis=None), column_config={"game_page": st.column_config.LinkColumn(), "team_focus_indicator": None}, hide_index=True)
	elif option == "Future":
		new_live_df = new_live_df[pd.to_datetime(new_live_df.game_date) >= actual_today]
		st.dataframe(new_live_df.style.apply(highlight_all_games, axis=None), column_config={"game_page": st.column_config.LinkColumn(), "team_focus_indicator": None}, hide_index=True)
	elif option == "Today":
		new_live_df = new_live_df[(pd.to_datetime(new_live_df.game_date) >= actual_today)] 
		new_live_df = new_live_df[(pd.to_datetime(new_live_df.game_date) == min(pd.to_datetime(new_live_df.game_date)))] 
		st.dataframe(new_live_df.style.apply(highlight_all_games, axis=None), column_config={"game_page": st.column_config.LinkColumn(), "team_focus_indicator": None}, hide_index=True)
        
        
	st.markdown("* upset pick games are :blue[blue] with the underdog seen in :blue[blue] and unanimously picked games are :grey[grey] with the favorite in :green[green].")
    
	st.markdown("""---""")
	st.header("Picks")
	
	selection_list_p, deselection_list_p = toggle_list("a")
	selection_list = np.insert(selection_list_p, 0, 'Game')

	#picks_dates_styled = picks_dates.style.apply(highlight_all_names, axis=None)

	columns_to_hide = ["game_date", "game_home_team", "game_away_team", "game_name", "winner", "loser"]+deselection_list_p
	none_list = [None]*len(columns_to_hide)
	column_hide_dict = dict(zip(columns_to_hide, none_list))
	
	if option == "All":
		st.dataframe(picks_dates.style.apply(highlight_all_names, axis=None), hide_index = True, column_config = column_hide_dict)
	elif option == "Future":
		picks_dates = picks_dates[pd.to_datetime(picks_dates.game_date) >= actual_today]
		st.dataframe(picks_dates.style.apply(highlight_all_names, axis=None), hide_index = True, column_config = column_hide_dict)
	elif option == "Today":
		picks_dates = picks_dates[(pd.to_datetime(picks_dates.game_date) >= actual_today)] 
		picks_dates = picks_dates[(pd.to_datetime(picks_dates.game_date) == min(pd.to_datetime(picks_dates.game_date)))]
		st.dataframe(picks_dates.style.apply(highlight_all_names, axis=None), hide_index = True, column_config = column_hide_dict)


with tab_mbcc_13:
	
	#### all charts (bar and 2 argyle)
	column_list = starting_people_list
	column_list.append('gametracker')
	
	# binary_tracker_df = pd.DataFrame(run_query(f'SELECT * FROM "{live_tracker_binary}"'))
	binary_tracker_df = live_tracker_binary
	# complex_tracker_df = pd.DataFrame(run_query(f'SELECT * FROM "{live_tracker_complex}"'))
	complex_tracker_df = live_tracker_complex

	binary_tracker_df = binary_tracker_df[column_list].apply(pd.to_numeric)
	complex_tracker_df = complex_tracker_df[column_list].apply(pd.to_numeric)
	
	
	tracker_list, detracker_list = toggle_list("b")
	st.header("Correct Picks")
	st.bar_chart(current_scores_df.iloc[0:1][tracker_list].T)


	st.header("Argyle Chart")
	st.line_chart(binary_tracker_df[binary_tracker_df.gametracker==1][tracker_list])
	st.markdown("""---""")
	st.header("Point Chaos Argyle Chart")
	st.line_chart(complex_tracker_df[complex_tracker_df.gametracker==1][tracker_list])


with tab_elimination:
	#full_score_df = pd.DataFrame(run_query(f'SELECT * FROM "{full_score_matrix}"'))
	#tracker_only = pd.DataFrame(run_query(f'SELECT * FROM "{live_tracker_binary}"'))[['gametracker']].tail(-1).reset_index()
	tracker_only = live_tracker_binary[['gametracker']].tail(-1).reset_index()

	# build data frame for representation of picks
	# st.dataframe(tracker_only)
	remaining_df = pd.concat([picks_df, tracker_only], axis = 1)

	unset_cfp_games = []
	
	# remove impossible picks
	full_game_set = set(live_df["game_name"]+live_df["game_home_team"])|set(live_df["game_name"]+live_df["game_away_team"])
	
	for i in full_game_set:
		if "TBD" in i:
			unset_cfp_games.append(i[:50])
	
	
	
	#st.write(unset_cfp_games)
	
	player_elimination_check = []
	full_elimination_matrix = {}
	for player in the_people_list:
		# setting the potential correct picks based on the player
		potential_correct_picks = set(remaining_df[remaining_df['gametracker']==0]["Game"]+remaining_df[remaining_df['gametracker']==0][player])

		impossible_games = []
		# remove games that can't be won since the competitor got eliminated in an earlier round
		for i in potential_correct_picks:
			if i[:50] not in unset_cfp_games:
				if i not in full_game_set:
					impossible_games.append(i)

		#st.write(impossible_games)

		for k in impossible_games:
			potential_correct_picks.remove(k)
		
		#st.write(potential_correct_picks)
					
		
		
		# adding in the current correct picks
		
		player_current_picks = main_score_df[main_score_df["Player"] == player]["Picks Correct"].values
		# st.write(potential_correct_picks)
		#st.write("person's picks")
		#st.write(player_current_picks)
		
		comparison_dict = {}
		for compare_player in the_people_list:
			player_picks = set(remaining_df[remaining_df['gametracker']==0]["Game"]+remaining_df[remaining_df['gametracker']==0][compare_player])
			# st.write(player_picks)
			# adding in correct picks currently for each individual
			compare_player_current_picks = main_score_df[main_score_df["Player"] == compare_player]["Picks Correct"].values
			# checks to see if the player's potential picks line up comparing players
			comparison_array = player_picks & potential_correct_picks
			# st.write(comparison_array)
			#st.write("picks in common with another person")
			#st.write(len(comparison_array))
			#st.write(compare_player_current_picks)
			#st.write(len(comparison_array)+compare_player_current_picks)
			comparison_dict[compare_player] = len(comparison_array)+compare_player_current_picks

		full_elimination_matrix[player] = comparison_dict

		### can calculate whether someone is eliminated here
		player_elimination_check.append(comparison_dict[player] == max(comparison_dict.values()))

	# st.write(full_elimination_matrix)
	
	
	# st.write(player_elimination_check)

	player_select = st.selectbox('Checking the elimination of which player?', the_people_list)
	player_index = the_people_list.index(player_select)
	if player_elimination_check[player_index]:
		st.markdown("NOT YET ELIMINATED")
	else:
		st.markdown("ELIMINATED")
	

	### turn dictionary into matrix or array to output

	st.header("Elimination Matrix!")

	elimination_matrix_creation = {}
	for player in the_people_list:
		elimination_matrix_creation[player] = full_elimination_matrix[player].values()

	# st.write(elimination_matrix_creation)
	
	## create the elimination matrix for display
	elim_mat_complete = pd.concat([pd.Series(the_people_list),pd.DataFrame.from_dict(elimination_matrix_creation)], axis=1)
	elim_mat_complete.columns = np.insert(the_people_list, 0, 'Player')
	new_elim_mat_complete = elim_mat_complete.set_index(['Player'])
	st.dataframe(new_elim_mat_complete)


with tab_history:
	st.header("Mehfoud Bowl Challenge Chalice History")
	#history_df = pd.DataFrame(run_query(f'SELECT * FROM "{history_sheet}"'))
	history_df = history_sheet
	
	player_list = history_df.Player.unique()
	player_list = np.insert(player_list, 0, 'All Players')
	
	history_df['Percentage Correct'] = history_df['PercentageCorrect'].apply(lambda x: x*100).map('{:.2f}%'.format)
	not_current = st.checkbox('show all players')
	not_winner = st.checkbox('show more than winners')
	option = st.selectbox('Select a Player', player_list)

	#agg_history = pd.DataFrame(run_query(f'SELECT * FROM "{agg_history}"'))
	agg_history = agg_history
	agg_history = agg_history[agg_history.Active == True]
	agg_history['Percentage Correct'] = agg_history['LivePercentage'].apply(lambda x: x*100).map('{:.2f}%'.format)
	agg_history['Live Wins'] = agg_history['LiveWins']
	agg_history['Live Losses'] = agg_history['LiveLosses']
	agg_history = agg_history[['Player', 'Live Wins', 'Live Losses', 'Percentage Correct']]

	#season_history = pd.DataFrame(run_query(f'SELECT * FROM "{season_history}"'))
	season_history = season_history
	season_history['Percentage Correct'] = season_history['Percentage'].apply(lambda x: x*100).map('{:.2f}%'.format)
	season_history['Total Wins'] = season_history['TotalWins']
	season_history['Total Losses'] = season_history['TotalLosses']
	season_history= season_history[['Season', 'Total Wins', 'Total Losses', 'Percentage Correct']]
	
	if not_current:
		if not_winner:
			history_df_rev = history_df[['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
		else:
			history_df_rev = history_df[(history_df['Winner'] == 'Winner') | (history_df['Winner'] == 'Co-Winner')][['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
	else:
		if not_winner:
			history_df_rev = history_df[(history_df['Current'] == True)][['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
		else:
			history_df_rev = history_df[(history_df['Current'] == True) & ((history_df['Winner'] == 'Winner') | (history_df['Winner'] == 'Co-Winner'))][['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
	
	if option == 'All Players':
		st.write("Player Season Breakdown")
		st.dataframe(history_df_rev.sort_values(by='MBCC'), hide_index=True)
		st.markdown("""---""")
		st.write("Player Career Breakdown")
		st.dataframe(agg_history, hide_index=True)
	
	else:
		st.write("Player Season Breakdown")
		st.dataframe(history_df_rev[history_df_rev.Player == option].sort_values(by='MBCC'), hide_index=True)
		st.markdown("""---""")
		st.write("Player Career Breakdown")
		st.dataframe(agg_history[agg_history.Player == option], hide_index=True)

	st.markdown("""---""")
	st.write("MBCC Season Breakdown")
	st.dataframe(season_history, hide_index=True)

# with sql_learning:
# 	st.markdown("""---""")
# 	st.write("Hello, let's learn some SQL")
# 	st.write("the asterisk gives us all columns after the SELECT, the table is called 'history_df' after the FROM -- here we see 'SELECT * FROM history_df LIMIT 5'")
# 	st.dataframe(ps.sqldf('SELECT * FROM history_df LIMIT 5'))
# 	st.write("The columns in the table are at the top -- MBCC, Player, Picks, Games, Percentage_Correct, Winner, Current, Percentage Correct")
# 	st.write("We only have 5 rows because we said LIMIT 5")
# 	st.write("Now we can select columns, do math with this, or filter it")
# 	st.write("'SELECT Player, Picks FROM history_df WHERE Picks < 20' will give us each person who picked less than 20 games correctly in a season using the WHERE as that filter indicator")
# 	st.dataframe(ps.sqldf('SELECT Player, Picks FROM history_df WHERE Picks < 20'))
# 	st.write("Now let's order it, then limit it... 'SELECT Player, Picks FROM history_df WHERE Picks < 20 ORDER BY PICKS LIMIT 5")
# 	st.dataframe(ps.sqldf('SELECT Player, Picks FROM history_df WHERE Picks < 20 ORDER BY PICKS LIMIT 5'))
# 	st.write("""uhoh, we're now only capturing this years picks, 
#  		because they're all zero already... 
#    		let's add a filter for the mbcc, 
#      		and since we're ordering the picks in ascending order (lowest to highest), 
#        		we don't need the less than 20 filter, 
# 	 	though we can use as many filters as we want
#    		-- 'WHERE MBCC <> '2023-2024 (12th MBCC)' -- <> means is not equal""")
# 	st.dataframe(ps.sqldf("SELECT Player, Picks FROM history_df WHERE MBCC <> '2023-2024 (12th MBCC)' ORDER BY PICKS LIMIT 5"))
# 	st.write("Now let's add up the picks - 'SELECT SUM(Picks) FROM history_df'")
# 	st.dataframe(ps.sqldf('SELECT SUM(Picks) FROM history_df'))
# 	st.write("OR find the minimum number of picks - 'SELECT MIN(Picks) FROM history_df WHERE MBCC <> '2023-2024 (12th MBCC)''")
# 	st.dataframe(ps.sqldf("SELECT MIN(Picks) FROM history_df WHERE MBCC <> '2023-2024 (12th MBCC)'"))
# 	st.write("We can see this result in the top of our ordered table on picks")
# 	st.write("Now let's using groupings --- 'SELECT Player, MAX(Picks) FROM history_df GROUP BY Player' tells us to take the max for each player")
# 	st.dataframe(ps.sqldf("SELECT Player, MAX(Picks) FROM history_df GROUP BY Player"))
# 	st.write("You can make it complicated by making smaller tables, and selecting from them, or joining on other tables")
# 	st.write("for example, you can look at the number of picks in the past few years of the people who selected a specific team this year (using picks_df once updated) or many other things")
# 	st.write("we can break down things more creatively once you've got those basics down, but type into the box below and press enter!")
	
# 	st.write("Try whatever you'd like:")
# 	text_input = st.text_input(
# 	        "Write your query here (SELECT * FROM history_df)",
#         	label_visibility="visible",
# 	        disabled=False,
#         	placeholder="QUERY",
#     		)
# 	st.dataframe(ps.sqldf(text_input))

with need_to_know:
	#st.header("Information")
	st.markdown("""
 	**Objective:**  \n
	- Pick the most games correctly. If you pick more correctly than anyone else, you win.  \n
  	- Root for your teams to win by as much as possible or lose by as few as possible when winning isn't an option.  \n
   		- In betting, your team can cover without winning, that's what this represents
	""")
	
	
	st.markdown("""**Tiebreakers** (only decides 1st vs 2nd):  \n
	1. Point Spread (points gained by wins, lost by losses, added together)  \n
	2. Upset Picks (number of upset picks predicted correctly)  \n
	3. Playoff Bracket Picks (number of playoff picks predicted correctly)  \n
	4. Potential Upset Picks (number of upset picks attempted, even if not correct)  \n
	5. Upset Pick Point Spread (point spread of correct upset picks)  \n
	6. Playoff Bracket Pick Point Spread (point spread of the playoff games)  \n
	7. Potential Upset Picks Point Spread (point spread of all attempted upset picks)  \n
 	8. MBCC Commemorative Coin Flip
	""")
	

	st.markdown("""**Winnings:**  \n
	1. First place gets $300 and their name on the trophy (determined by most picks correct and tiebreaker if needed)  \n
 	2. Second place gets about $150 (whatever is in the change jar) (determined by best point spread)  \n
  	3. Hokie Prize $300 split between those who beat Papa Smurf's number of wins  \n
	""")

	st.markdown("**Last Year's Winner:**")
	image = Image.open("last_years_winner.png")

	st.image(image, caption = "Last year's winner - Christopher!", width = 300)



st.write("MBCC 11 Winner was Lauren -- got problems with that, email mehfoudbowlchallengechalice@gmail.com -- check out the Information; almost as cool, MBCC 12 was won by Christopher")

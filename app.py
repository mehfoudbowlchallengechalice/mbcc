import streamlit as st
import pandas as pd
import pandasql as ps
from google.oauth2 import service_account
import numpy as np
import matplotlib.pyplot as plt
import plotly.figure_factory as ff
import plotly.express as px
import plotly.graph_objs as go
from live_results_scrape import get_schedule
from toggles import toggle_list
from people_list import people_list
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression
import datetime
import streamlit as st
from google.oauth2 import service_account
from gsheetsdb import connect

st.set_page_config(layout="wide")

st.write ("""
## TEASER FOR MBCC 12 in 2023-24!!
""")


###TODO:: add line at the bottom for Lauren being the current winner, and then a line to show who's currently in the lead
###TODO:: add games in, games left

######### DOWN BELOW --- add in elimination check process

##TODO drop down here for players
## set option to have current winner in bold

# Create a connection object.
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
    ],
)
conn = connect(credentials=credentials)

st.cache_data(ttl=600)
def run_query(query):
    rows = conn.execute(query, headers=1)
    rows = rows.fetchall()
    return rows

### change this in december!!!
st.cache_data(ttl=60000)
def bring_in_live_games():
    return get_schedule()



current_scores = st.secrets["current_pick_success"]
history_sheet = st.secrets["history_sheet"]
agg_history = st.secrets["agg_history"]
season_history = st.secrets["season_history"]
picks = st.secrets["picks"]
unlive_games = st.secrets["unlive_games"]
live_tracker_binary = st.secrets["live_tracker_binary"]
live_tracker_complex = st.secrets["live_tracker_complex"]
#full_score_matrix = st.secrets["full_pick_summary"]


starting_people_list = people_list()
the_people_list = people_list()
current_scores_df = pd.DataFrame(run_query(f'SELECT * FROM "{current_scores}"'))

### creation of the columns
col1,col2 = st.columns(2)

#main score
main_score_df = current_scores_df[current_scores_df["Situation"]=="mbcc_score"].T.rename_axis('Situation').reset_index()
main_score_df = main_score_df[1:]
main_score_df.columns = ["Player", "Overall Score"]

main_score_df["Overall Rank"] = main_score_df["Overall Score"].rank(ascending = False)
main_score_df.sort_values(by=["Overall Rank"])

#point difference score
point_diff_score_df = current_scores_df[current_scores_df["Situation"]=="point_difference"].T.rename_axis('Situation').reset_index()
point_diff_score_df = point_diff_score_df[1:]
point_diff_score_df.columns = ["Player", "Point Difference"]

point_diff_score_df["Point Difference Rank"] = point_diff_score_df["Point Difference"].rank(ascending = False)
point_diff_score_df.sort_values(by=["Point Difference Rank"])

with col1:
	st.header("Overall Score")
	st.dataframe(main_score_df, hide_index=True)

with col2:
	st.header("Point Difference Score")
	st.dataframe(point_diff_score_df, hide_index=True)


### creation of the tabs
tab_today, tab12, tab_elimination, tab_history = st.tabs(["Live", "MBCC 12", "Elimination Check??", "History"])


with tab_today:
	st.header("Games")
	#live_df = bring_in_live_games()
	live_df = pd.DataFrame(run_query(f'SELECT * FROM "{unlive_games}"'))

	# bringing in picks
	picks_df = pd.DataFrame(run_query(f'SELECT * FROM "{picks}"'))
	picks_dates = picks_df.merge(live_df[["game_name", "game_date"]], left_on = "Game", right_on = "game_name")
	
	### today, future, all drop down to show picks
	option = st.selectbox("Select Games to See", ("Today", "Future", "All"))
	
	if option == "All":
		st.dataframe(live_df, hide_index=True)
	elif option == "Future":
		st.dataframe(live_df[pd.to_datetime(live_df.game_date) >= datetime.datetime.today()], hide_index=True)
	elif option == "Today":
		st.dataframe(live_df[(pd.to_datetime(live_df.game_date) >= datetime.datetime.today()) 
        			& (pd.to_datetime(live_df.game_date) == min(pd.to_datetime(live_df.game_date)))], hide_index=True)
	
	st.markdown("""---""")
	st.header("Picks")
	####TODO: CONDITIONAL FORMATTING POSSIBLE HERE????????
	selection_list = toggle_list("a")
	selection_list = np.insert(selection_list, 0, 'Game')

	if option == "All":
		st.dataframe(picks_dates[selection_list])
	elif option == "Future":
		st.dataframe(picks_dates[pd.to_datetime(picks_dates.game_date) >= datetime.datetime.today()][selection_list])
	elif option == "Today":
		st.dataframe(picks_dates[(pd.to_datetime(picks_dates.game_date) >= datetime.datetime.today()) 
        			& (pd.to_datetime(picks_dates.game_date) == min(pd.to_datetime(picks_dates.game_date)))][selection_list])

with tab12:
	
	#### all charts (bar and 2 argyle)
	column_list = starting_people_list
	column_list.append('gametracker')
	binary_tracker_df = pd.DataFrame(run_query(f'SELECT * FROM "{live_tracker_binary}"'))
	complex_tracker_df = pd.DataFrame(run_query(f'SELECT * FROM "{live_tracker_complex}"'))

	binary_tracker_df = binary_tracker_df[column_list].apply(pd.to_numeric)
	complex_tracker_df = complex_tracker_df[column_list].apply(pd.to_numeric)
	
	
	tracker_list = toggle_list("b")
	st.header("Correct Picks")
	st.bar_chart(current_scores_df.iloc[0:1][tracker_list].T)


	st.header("Argyle Chart")
	st.line_chart(binary_tracker_df[binary_tracker_df.gametracker==1][tracker_list])
	st.markdown("""---""")
	st.header("Point Chaos Argyle Chart")
	st.line_chart(complex_tracker_df[complex_tracker_df.gametracker==1][tracker_list])


with tab_elimination:
	#full_score_df = pd.DataFrame(run_query(f'SELECT * FROM "{full_score_matrix}"'))
	tracker_only = pd.DataFrame(run_query(f'SELECT * FROM "{live_tracker_binary}"'))[['gametracker']].tail(-1).reset_index()

	# build data frame for representation of picks
	# st.dataframe(tracker_only)
	remaining_df = pd.concat([picks_df, tracker_only], axis = 1)
	
	
	st.markdown(the_people_list)
	player_elimination_check = []
	full_elimination_matrix = {}
	for player in the_people_list:
		# setting the correct picks based on the player
		potential_correct_picks = set(remaining_df[remaining_df['gametracker']==0]["Game"]+remaining_df[remaining_df['gametracker']==0][player])
		comparison_dict = {}
		for compare_player in the_people_list:
			player_picks = set(remaining_df[remaining_df['gametracker']==0]["Game"]+remaining_df[remaining_df['gametracker']==0][compare_player])
			comparison_dict[compare_player] = len(player_picks & potential_correct_picks)

		full_elimination_matrix[player] = comparison_dict

		### can calculate whether someone is eliminated here
		player_elimination_check.append(comparison_dict[player] == max(comparison_dict.values()))


	st.markdown(player_elimination_check)

	player_select = st.selectbox('Checking the elimination of which player?', the_people_list)
	player_index = the_people_list.index(player_select)
	if player_elimination_check[player_index]:
		st.markdown("NOT YET ELIMINATED")
	else:
		st.markdown("ELIMINATED")
	
	st.markdown(full_elimination_matrix)
	st.dataframe(remaining_df)

	### turn dictionary into matrix or array to output

	elimination_matrix_creation = {}
	for player in the_people_list:
		elimination_matrix_creation[player] = full_elimination_matrix[player].values()

	elim_mat_complete = pd.concat([pd.Series(the_people_list),pd.DataFrame.from_dict(elimination_matrix_creation)], axis=1)
	elim_mat_complete.columns = 'Player' + the_people_list
	st.dataframe(elim_mat_complete)
	st.dataframe(elim_mat_complete.set_index(['Player'], inplace = True))
	#st.dataframe(pd.DataFrame.from_dict(elimination_matrix_creation, index = the_people_list))


with tab_history:
	st.header("Mehfoud Bowl Challenge Chalice History")
	history_df = pd.DataFrame(run_query(f'SELECT * FROM "{history_sheet}"'))
	player_list = history_df.Player.unique()
	player_list = np.insert(player_list, 0, 'All Players')
	history_df['Percentage Correct'] = history_df['Percentage_Correct'].apply(lambda x: x*100).map('{:.2f}%'.format)
	not_current = st.checkbox('show all players')
	not_winner = st.checkbox('show more than winners')
	option = st.selectbox('Select a Player', player_list)

	agg_history = pd.DataFrame(run_query(f'SELECT * FROM "{agg_history}"'))
	agg_history = agg_history[agg_history.Active == True]
	agg_history['Percentage Correct'] = agg_history['Live_Percentage'].apply(lambda x: x*100).map('{:.2f}%'.format)
	agg_history = agg_history[['Player', 'Live_Wins', 'Live_Losses', 'Percentage Correct']]

	season_history = pd.DataFrame(run_query(f'SELECT * FROM "{season_history}"'))
	season_history['Percentage Correct'] = season_history['Percentage'].apply(lambda x: x*100).map('{:.2f}%'.format)
	season_history= season_history[['Season', 'Total_Wins', 'Total_Losses', 'Percentage Correct']]
	
	if not_current:
		if not_winner:
			history_df_rev = history_df[['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
		else:
			history_df_rev = history_df[(history_df['Current'] == True) & ((history_df['Winner'] == 'Winner') | (history_df['Winner'] == 'Co-Winner'))][['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
	else:
		if not_winner:
			history_df_rev = history_df[(history_df['Current'] == True)][['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')
		else:
			history_df_rev = history_df[(history_df['Winner'] == 'Winner') | (history_df['Winner'] == 'Co-Winner')][['MBCC', 'Player', 'Picks', 'Games', 'Percentage Correct', 'Winner']].sort_values(by='MBCC')

	
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
		
	##TODO drop down for specific MBCC

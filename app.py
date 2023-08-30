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
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression
import datetime
import streamlit as st
from google.oauth2 import service_account
from gsheetsdb import connect

st.write ("""
## TEASER FOR MBCC 12 in 2023-24!!
""")

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




history_sheet = st.secrets["history_sheet"]
agg_history = st.secrets["agg_history"]
season_history = st.secrets["season_history"]
picks = st.secrets["picks"]
unlive_games = st.secrets["unlive_games"]


tabtoday, tab2, tab1, tabhistory = st.tabs(["Live", "MBCC 12", "Elimination Check??", "History"])




with tabtoday:
	st.header("Games Today")
	#live_df = bring_in_live_games()
	live_df = pd.DataFrame(run_query(f'SELECT * FROM "{unlive_games}"'))

	# bringing in picks
	picks_df = pd.DataFrame(run_query(f'SELECT * FROM "{picks}"'))
	picks_dates = picks_df.merge(live_df[["game_name", "game_date"]], left_on = "Game", right_on = "game_name")
	
	### add in today, future, all drop down
	option = st.selectbox("Select Games to See", ("Today", "Future", "All"))
	
	if option == "All":
		st.dataframe(live_df, hide_index=True)
	elif option == "Future":
		st.dataframe(live_df[pd.to_datetime(live_df.game_date) >= datetime.datetime.today()], hide_index=True)
	elif option == "Today":
		st.dataframe(live_df[(pd.to_datetime(live_df.game_date) >= datetime.datetime.today()) 
        			& (pd.to_datetime(live_df.game_date) == min(pd.to_datetime(live_df.game_date)))], hide_index=True)

	checks = st.columns(5)
	with checks[0]:
		option_cr = st.checkbox("Christopher", value = True)
		option_ee = st.checkbox("Elise", value = True)
	with checks[1]:
		option_ea = st.checkbox("Emma", value = True)
		option_gy = st.checkbox("Gregory", value = True)
	with checks[2]:
		option_jn = st.checkbox("Jen", value = True)
		option_jh = st.checkbox("Joseph", value = True)
	with checks[3]:
		option_la = st.checkbox("Laura", value = True)
		option_ln = st.checkbox("Lauren", value = True)
	with checks[4]:
		option_ns = st.checkbox("Nicholas", value = True)
		option_pf = st.checkbox("P Smurf", value = True)

	people_list = ["Christopher", "Elise", "Emma", "Gregory", "Jen", "Joseph", "Laura", "Lauren", "Nicholas", "P Smurf"]
	collection_df = pd.DataFrame(list(zip(people_list, [option_cr, option_ee, option_ea, option_gy, option_jn, option_jh, option_la, option_ln, option_ns, option_pf])))
	st.write(collection_df[collection_df[1] == True][0].values.tolist())
	
with tabhistory:
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

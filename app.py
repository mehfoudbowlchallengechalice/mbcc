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

st.write ("""
Pick a player
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
unlive_games = st.secrets["unlive_games"]

tabtoday, tab2, tab1, tabhistory = st.tabs(["Live", "MBCC 12", "Elimination Check??", "History"])




with tabtoday:
	st.header("Games Today")
	#live_df = bring_in_live_games()
	live_df = pd.DataFrame(run_query(f'SELECT * FROM "{unlive_games}"'))
	
	#TODO -- add detail for the spreadsheet for all games
	
	### add in today, future, all drop down
	option = st.selectbox("Select Games to See", ("Today", "Future", "All"))

	if option == "All":
		st.dataframe(live_df, hide_index=True)
	elif option == "Future":
		st.dataframe(live_df[pd.to_datetime(live_df.game_date) >= datetime.datetime.today()], hide_index=True)
	elif option == "Today":
		st.dataframe(live_df[(pd.to_datetime(live_df.game_date) >= datetime.datetime.today()) 
        			& (pd.to_datetime(live_df.game_date) == min(pd.to_datetime(live_df.game_date)))], hide_index=True)
	
with tabhistory:
	st.header("Mehfoud Bowl Challenge Chalice History")
	history_df = pd.DataFrame(run_query(f'SELECT * FROM "{history_sheet}"'))
	history_df['Percentage Correct'] = 100*history_df['Percentage_Correct'].map('{:.2f}%'.format)
	history_df['MBCC Title'] = history_df['MBCC_Title']
	history_df_rev = history_df[['MBCC Title', 'Winner', 'Picks', 'Games', 'Percentage Correct']]
	st.dataframe(history_df_rev)

	##TODO drop down for specific MBCC

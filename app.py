import streamlit as st
import pandas as pd
import pandasql as ps
from google.oauth2 import service_account
import numpy as np
import matplotlib.pyplot as plt
import plotly.figure_factory as ff
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression
import streamlit as st
from google.oauth2 import service_account
from gsheetsdb import connect

st.write ("""
## TEASER FOR MBCC 12 in 2023-24!!
""")

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

history_sheet = st.secrets["history_sheet"]

tab3, tab2, tab1 = st.tabs(["Live", "MBCC 12", "History"])

with tab3:
	st.header("Mehfoud Bowl Challenge Chalice History")
	rows = run_query(f'SELECT * FROM "{history_sheet}"')


    
	st.dataframe(rows)


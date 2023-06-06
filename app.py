import streamlit as st
import pandas as pd
import pandasql as ps
from google.oauth2 import service_account
import gspread
import numpy as np
import matplotlib.pyplot as plt
import plotly.figure_factory as ff
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression

st.write ("""
## THE BASE COAT FOR MBCC 12 in 23-24!!
""")

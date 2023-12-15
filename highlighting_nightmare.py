import numpy as np
import pandas as pd
import streamlit as st
### this will help, because damn
####https://stackoverflow.com/questions/41203959/conditionally-format-python-pandas-cell
### data frame conditioning
def highlight_all_names(x):
  color_codes = pd.DataFrame('', index=x.index, columns=x.columns)
  color_codes['Christopher'] = np.where(x['Christopher'] == x['winner'], "color: green", 
                                        np.where(x['Christopher'] == x['loser'], "color:red", ""))
  color_codes['Nicholas'] = np.where(x['Nicholas'] == x['winner'], "color: green", 
                                        np.where(x['Nicholas'] == x['loser'], "color:red", ""))
  color_codes['Joseph'] = np.where(x['Joseph'] == x['winner'], "color: green", 
                                        np.where(x['Joseph'] == x['loser'], "color:red", ""))
  color_codes['Gregory'] = np.where(x['Gregory'] == x['winner'], "color: green", 
                                        np.where(x['Gregory'] == x['loser'], "color:red", ""))
  color_codes['Emma'] = np.where(x['Emma'] == x['winner'], "color: green", 
                                        np.where(x['Emma'] == x['loser'], "color:red", ""))
  color_codes['Elise'] = np.where(x['Elise'] == x['winner'], "color: green", 
                                        np.where(x['Elise'] == x['loser'], "color:red", ""))
  color_codes['Laura'] = np.where(x['Laura'] == x['winner'], "color: green", 
                                        np.where(x['Laura'] == x['loser'], "color:red", ""))
  color_codes['Lauren'] = np.where(x['Lauren'] == x['winner'], "color: green", 
                                        np.where(x['Lauren'] == x['loser'], "color:red", ""))
  color_codes['PSmurf'] = np.where(x['PSmurf'] == x['winner'], "color: green", 
                                        np.where(x['PSmurf'] == x['loser'], "color:red", ""))
  color_codes['Jen'] = np.where(x['Jen'] == x['winner'], "color: green", 
                                        np.where(x['Jen'] == x['loser'], "color:red", ""))
  return color_codes

def highlight_all_games(x):
  font_codes = pd.DataFrame('', index=x.index, columns=x.columns)
  font_codes['game_name'] = np.where(x['upset_indicator'] == 1, "color: purple", "")
  font_codes['game_name'] = np.where(x['unanimous_indicator'] == 1, "color: gray", "")
  
  return font_codes


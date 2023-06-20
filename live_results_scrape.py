import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import datetime

def get_schedule():
  """Gets the College Football Schedule for Week 1 of the 2023 season."""
  url_1 = "https://www.espn.com/college-football/schedule/_/week/1/year/2023/seasontype/3"
  response_1 = requests.get(url_1)
  soup_1 = BeautifulSoup(response_1.content, "html.parser")

  df_main = organize_soup(soup_1)

  url_2 = "https://www.espn.com/college-football/schedule/_/week/1/year/2023/seasontype/3/group/81"
  response_2 = requests.get(url_2)
  soup_2 = BeautifulSoup(response_2.content, "html.parser")

  df_fcs = organize_soup(soup_2)
    
  final_df = df_main.append(df_fcs)
  final_df['game_timestamp'] = pd.to_datetime(final_df.game_date+' '+final_df.game_time, format = "%A, %B %d, %Y %I:%M %p")
  final_df = final_df.sort_values(by = ['game_timestamp'])

  return final_df

    
def organize_soup(soup):
#   print(soup)
  # games 

  ## gathering the string and index
  ind = []
  str_name = []
  str_type = []
    
  table_games = soup.find_all("span", {"class": "gameNote pt3"}) 
  #print(table_games)
  for row in table_games:
    ind.append(row.sourcepos)
    str_name.append(row.get_text(strip=True))
    str_type.append('game')
  
  table_away_teams = soup.find_all("span", {"class": "Table__Team away"})
  for row in table_away_teams:
    ind.append(row.sourcepos)
    str_name.append(row.get_text(strip=True))
    str_type.append('away_team')
    
  table_home_teams = soup.find_all("span", {"class": "Table__Team"})
  for row in table_home_teams:
    if ("away" not in str(row)):
      ind.append(row.sourcepos)
      str_name.append(row.get_text(strip=True))
      str_type.append('home_team')
    
  table_venues = soup.find_all("td", {"class": "venue__col Table__TD"})
  #print(table_venues)
  for row in table_venues:
    ind.append(row.sourcepos)
    str_name.append(row.get_text(strip=True))
    str_type.append('venue')
    
  table_dates = soup.find_all("div", {"class": "Table__Title"})
  #print(table_venues)
  for row in table_dates:
    ind.append(row.sourcepos)
    str_name.append(row.get_text(strip=True))
    str_type.append('date')

  table_times = soup.find_all("a", {"class": "AnchorLink", "href": re.compile('/college-football/game*'), "tabindex":"0"})
  #print(table_venues)
  for row in table_times:
    ind.append(row.sourcepos)
    str_name.append(row.get_text(strip=True))
    str_type.append('time')
    

  df = pd.DataFrame({
      'ind': ind,
      'data': str_name,
      'type': str_type
  })

  df_ordered = df.sort_values(by=['ind'])
   
  date_list = []
  time_list = []
  game_list = []
  venue_list = []
  home_team = []
  away_team = []
  
    
  for row in df_ordered.iterrows():
    if row[1][2] == 'date':
      date_1 = row[1][1]
    if row[1][2] == 'game':
      game_list.append(row[1][1])
      date_list.append(date_1)
    if row[1][2] == 'time':
      time_list.append(row[1][1])
    if row[1][2] == 'venue':
      venue_list.append(row[1][1])
    if row[1][2] == 'away_team':
      away_team.append(row[1][1])
    if row[1][2] == 'home_team':
      home_team.append(row[1][1])
    
  df_final = pd.DataFrame({
      'game_date': date_list,
      'game_time': time_list,
      'game_name': game_list,
      'game_venue': venue_list,
      'game_home_team': home_team,
      'game_away_team': away_team
  })
                
  return df_final

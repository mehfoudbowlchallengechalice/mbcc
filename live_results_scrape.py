import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def get_schedule():
  """Gets the College Football Schedule for Week 1 of the 2023 season."""
  url = "https://www.espn.com/college-football/schedule/_/week/1/year/2023/seasontype/3"
  response = requests.get(url)
  soup = BeautifulSoup(response.content, "html.parser")

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

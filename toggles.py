import streamlit as st
import numpy as np
import pandas as pd
from people_list import people_list


def toggle_list(i):
	checks = st.columns(5)
	with checks[0]:
		option_cr = st.toggle("Christopher", value = True, key = "cr"+i)
		option_ee = st.toggle("Elise", value = True, key = "ee"+i)
	with checks[1]:
		option_ea = st.toggle("Emma", value = True, key = "ea"+i)
		option_gy = st.toggle("Gregory", value = True, key = "gy"+i)
	with checks[2]:
		option_jn = st.toggle("Jen", value = True, key = "jn"+i)
		option_jh = st.toggle("Joseph", value = True, key = "jh"+i)
	with checks[3]:
		option_la = st.toggle("Laura", value = True, key = "la"+i)
		option_ln = st.toggle("Lauren", value = True, key = "ln"+i)
	with checks[4]:
		option_ns = st.toggle("Nicholas", value = True, key = "ns"+i)
		option_pi = st.toggle("Poppi", value = True, key = "pi"+i)

	set_people_list = people_list()
	collection_df = pd.DataFrame(list(zip(set_people_list, [option_cr, option_ee, option_ea, option_gy, option_jn, option_jh, option_la, option_ln, option_ns, option_pi])))
	selection_list = collection_df[collection_df[1] == True][0].values.tolist()
	deselection_list = collection_df[collection_df[1] == False][0].values.tolist()
	
	return selection_list, deselection_list
        

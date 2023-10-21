import streamlit as st
import numpy as np
import pandas as pd


def toggle_list():
	checks = st.columns(5)
		with checks[0]:
			option_cr = st.toggle("Christopher", value = True)
			option_ee = st.toggle("Elise", value = True)
		with checks[1]:
			option_ea = st.toggle("Emma", value = True)
			option_gy = st.toggle("Gregory", value = True)
		with checks[2]:
			option_jn = st.toggle("Jen", value = True)
			option_jh = st.toggle("Joseph", value = True)
		with checks[3]:
			option_la = st.toggle("Laura", value = True)
			option_ln = st.toggle("Lauren", value = True)
		with checks[4]:
			option_ns = st.toggle("Nicholas", value = True)
			option_pf = st.toggle("PSmurf", value = True)
    
		people_list = ["Christopher", "Elise", "Emma", "Gregory", "Jen", "Joseph", "Laura", "Lauren", "Nicholas", "PSmurf"]
		collection_df = pd.DataFrame(list(zip(people_list, [option_cr, option_ee, option_ea, option_gy, option_jn, option_jh, option_la, option_ln, option_ns, option_pf])))
		selection_list = collection_df[collection_df[1] == True][0].values.tolist()
		return selection_list
        

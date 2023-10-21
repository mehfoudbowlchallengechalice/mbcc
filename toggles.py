import streamlit as st
import numpy as np
import pandas as pd

## i creates the version of toggles so that we can use this function for multiple toggles
def toggle_list(i):
	checks = st.columns(5)
	with checks[0]:
		exec("option_cr"+i+" = st.toggle('Christopher', value = True)")
		exec("option_ee"+i+" = st.toggle('Elise', value = True)")
	with checks[1]:
		exec("option_ea"+i+" = st.toggle('Emma', value = True)")
		exec("option_gy"+i+" = st.toggle('Gregory', value = True)")
	with checks[2]:
		exec("option_jn"+i+" = st.toggle('Jen', value = True)")
		exec("option_jh"+i+" = st.toggle('Joseph', value = True)")
	with checks[3]:
		exec("option_la"+i+" = st.toggle('Laura', value = True)")
		exec("option_ln"+i+" = st.toggle('Lauren', value = True)")
	with checks[4]:
		exec("option_ns"+i+" = st.toggle('Nicholas', value = True)")
		exec("option_pf"+i+" = st.toggle('PSmurf', value = True)")

	print(option_cra)
	exec("variable_list = [option_cr"+i+", option_ee"+i+", option_ea"+i+", option_gy"+i+", option_jn"+i+", option_jh"+i+", option_la"+i+", option_ln"+i+", option_ns"+i+", option_pf"+i+"]")
	print(variable_list)
	people_list = ["Christopher", "Elise", "Emma", "Gregory", "Jen", "Joseph", "Laura", "Lauren", "Nicholas", "PSmurf"]
	collection_df = pd.DataFrame(list(zip(people_list, variable_list)))
	selection_list = collection_df[collection_df[1] == True][0].values.tolist()
	return selection_list
        

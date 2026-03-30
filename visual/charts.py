import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st



def plot_bar(series: pd.Series, title: str):
    fig, ax = plt.subplots(figsize=(10, 4))
    series.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)



def plot_line(series: pd.Series, title: str):
    fig, ax = plt.subplots(figsize=(10, 4))
    series.plot(kind="line", marker="o", ax=ax)
    ax.set_title(title)
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

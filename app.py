import streamlit as st
from pages import 1_Grupo, 2_Desafio, 3_Base_Histórica, 4_Previsão, 5_Insights_e_Conclusão

# Mapeamento das páginas
PAGES = {
    "Home": Home,
    "Grupo": 1_Grupo,
    "Desafio": 2_Desafio,
    "Base Histórica": 3_Relatório_Analitico_Preditivo,
    "Previsão": 4_Previsão,
    "Insights e Conclusão": 5_Insights_e_Conclusão,
}

def main():
    st.sidebar.title('Menu de Navegação')
    selection = st.sidebar.radio("Ir para", list(PAGES.keys()))
    
    page = PAGES[selection]
    page.app()

if __name__ == "__main__":
    main()

import streamlit as st
import ipeadatapy as ip
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import locale
import os
from PIL import Image

# Definir localidade para Português do Brasil
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    print("Locale pt_BR.UTF-8 não está disponível. Usando o padrão.")

st.title('Previsão com ML')

# Criação das abas
introducao, tab1, tab2 = st.tabs(["Introdução e etapas", "Previsão ML D+1", "Previsão ML D+10"])

with introducao:
    st.markdown("""
    # Introdução e Etapas
    """)

    st.markdown("""
    O modelo Random Forest Regressor foi utilizado devido à sua capacidade de lidar com relações complexas e não lineares entre variáveis, sua robustez contra overfitting, e a habilidade de fornecer previsões precisas mesmo com dados ausentes. Além disso, o modelo permite a identificação da importância das variáveis preditoras, facilitando a análise dos principais fatores que influenciam os preços do barril de petróleo Brent. Essa escolha garante previsões mais confiáveis em um mercado altamente volátil.
    """)

    st.markdown("""
    O resultado da predição foi avaliado utilizando as métricas MAE, MAPE e R². O MAE quantifica o erro médio absoluto, o MAPE fornece a precisão percentual das previsões, e o R² mede a proporção da variância explicada pelo modelo. Essas métricas foram escolhidas para garantir uma avaliação abrangente da precisão e eficácia do modelo na predição dos preços do barril de petróleo Brent.
    """)

    st.markdown("""
    Um gráfico foi gerado para mostrar o peso de cada feature do modelo, permitindo identificar os principais fatores que influenciam os preços do barril de petróleo Brent. O objetivo dessa visualização é facilitar a interpretação dos resultados, destacando quais variáveis têm maior impacto nas previsões, e, assim, orientar a tomada de decisões baseada em dados.
    """)

with tab1:
    st.markdown("""
    # Previsão D+1 do Petróleo Brent
    """)
    # Criação de um placeholder para a mensagem de carregamento
    loading_message = st.empty()
    loading_message.markdown("""
    Carregando (pode demorar um pouco)
    """)

    # Carregando dados de série temporal
    series = ip.list_series()
    data = ip.timeseries('EIA366_PBRENT366')
    data = data[["VALUE (US$)"]]
    data.rename(columns={"VALUE (US$)": "Price"}, inplace=True)
    data.index.name = "date"
    data = data.dropna()
    data.index = pd.to_datetime(data.index)
    
    # Filtrando os últimos 25 anos
    last_date = data.index[-1]
    filtrado = last_date - pd.DateOffset(years=25)
    filtrado25 = data.loc[filtrado:]
    
    # Divisão manual dos dados de treino e teste
    train_size = int(len(filtrado25) * 0.9)
    train, test = filtrado25.iloc[:train_size], filtrado25.iloc[train_size:]
    
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.experimental import enable_halving_search_cv  # noqa
    from sklearn.model_selection import HalvingGridSearchCV
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.base import BaseEstimator, TransformerMixin

    # Classe customizada para engenharia de features
    class FeatureEngineer(BaseEstimator, TransformerMixin):
        def __init__(self, target, lags, window_size):
            self.target = target
            self.lags = lags
            self.window_size = window_size

        def fit(self, X, y=None):
            return self

        def transform(self, X):
            X = X.copy()
            for lag in range(1, self.lags + 1):
                X[f"lag_{lag}"] = X[self.target].shift(lag)
            X[f"rolling_mean_{self.window_size}"] = X[self.target].shift(1).rolling(window=self.window_size).mean()
            X["diff"] = X[self.target].shift(1).diff()
            X["month"] = X.index.month
            X["day_of_week"] = X.index.dayofweek
            X[f"rolling_std_{self.window_size}"] = X[self.target].shift(1).rolling(window=self.window_size).std()
            X["day"] = X.index.day
            X["quarter"] = X.index.quarter
            X["year"] = X.index.year
            X = X.drop(columns=[self.target])
            X.fillna(0, inplace=True)
            return X

    # Pipeline de steps
    pipeline = Pipeline([
        ("feature_engineering", FeatureEngineer(target="Price", lags=7, window_size=7)),
        ("scaler", StandardScaler()),
        ("model", RandomForestRegressor())
    ])

    # Espaço amostral de hiperparâmetros
    param_grid = {
        "model__n_estimators": [100, 200],
        "model__max_depth": [10, 20],
        "model__min_samples_split": [2, 5],
        "model__max_features": ['auto', 'sqrt'],
        "model__bootstrap": [True, False]
    }

    # TimeSeriesSplit para validação cruzada
    tscv = TimeSeriesSplit(n_splits=3)

    # HalvingGridSearchCV para busca de melhor combinação de hiperparâmetros
    search = HalvingGridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        cv=tscv,
        factor=3,
        scoring="neg_mean_squared_error",
        verbose=1,
        n_jobs=-1
    )

    X = train.copy()
    y = train["Price"]

    # Fit do modelo
    search.fit(X, y)

    # Acessando o melhor modelo encontrado
    best_model = search.best_estimator_

    # Extraindo o transformador de engenharia de features
    feature_engineering = best_model.named_steps["feature_engineering"]

    # Transformando X para obter o nome das features geradas
    X_transformed = feature_engineering.transform(X)
    feature_names = X_transformed.columns

    # Acessando as importâncias das features
    importances = best_model.named_steps["model"].feature_importances_

    # DataFrame para as importâncias das features
    importance_df = pd.DataFrame({
        "Feature": feature_names,
        "Importance": importances
    }).sort_values(by="Importance", ascending=False)
    
    from sklearn.metrics import (
        mean_absolute_error,
        mean_absolute_percentage_error,
        r2_score
    )
    import plotly.graph_objects as go

    # Extraindo as features e o target
    X_test = test.copy()
    y_test = test["Price"]

    # Previsões no conjunto de teste
    y_pred = search.predict(X_test)

    # Avaliação da performance
    mae = mean_absolute_error(y_test, y_pred)
    mape = mean_absolute_percentage_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Plot das previsões vs valores reais
    y_test_index = y_test.index
    y_test_values = y_test.values.flatten()
    y_pred_values = y_pred.flatten()

    fig2 = go.Figure()

    # Adicionando os dados reais
    fig2.add_trace(go.Scatter(x=y_test_index, y=y_test_values,
                          mode='lines', name='Real',
                          line=dict(color='cyan')))

    # Adicionando as previsões
    fig2.add_trace(go.Scatter(x=y_test_index, y=y_pred_values,
                            mode='lines', name='Previsões D+1', line=dict(dash='dash',color='red')))

    # Atualizando layout do gráfico
    fig2.update_layout(title='Série Temporal - EIA366_PBRENT366',
                    xaxis_title='Data',
                    yaxis_title='US$',
                    legend=dict(x=0, y=1),
                    hovermode='x unified')
    
    # Criação do gráfico de barras das features usando Plotly
    fig1 = go.Figure()

    # Adicionando os dados de importância das features
    fig1.add_trace(go.Bar(
        y=importance_df["Feature"],
        x=importance_df["Importance"],
        orientation='h',
        marker=dict(color='lightcoral')
    ))

    # Atualizando layout do gráfico de barras
    fig1.update_layout(
        title='Importância de Features',
        xaxis_title='Importância',
        yaxis_title='Features',
        yaxis=dict(autorange='reversed'),  # Inverter o eixo y para a feature mais importante aparecer no topo
        plot_bgcolor='rgba(0,0,0,0)',  # Fundo transparente
        paper_bgcolor='rgba(0,0,0,0)'  # Fundo transparente
    )
    
    st.markdown("""
    ## Gráfico Previsão vs Dados reais:
    A seguir pode ser visto o gráfico da previsão efetuada pelo modelo, e os dados reais do conjunto de teste (últimos 10% do dataset)
    """)
    st.plotly_chart(fig2)
    st.markdown("""
    ## Métricas de avaliação da previsão:
    """)
    
    # Formatando os valores
    mae_formatted = f"{mae:.2f}"
    mape_formatted = f"{mape * 100:.2f}%"
    r2_formatted = f"{r2 * 100:.2f}%"  # Convertendo r2 para porcentagem
    col1, col2, col3 = st.columns(3)

    col1.metric(label="Mean Absolute Error", value=mae_formatted)
    col2.metric(label="Mean Absolute Percentage Error", value=mape_formatted)
    col3.metric(label="R² Score", value=r2_formatted)
    
    st.markdown("""
    ## Importância de cada feature para o modelo
    No gráfico a seguir pode ser visto a importância de cada feature para que o modelo execute a previsão, aonde lag_x é o dado do dia anterior em x dias e rolling_mean é a média dos últimos 7 dias.
    """)
    st.plotly_chart(fig1)
    # Removendo a mensagem de carregamento após o processo ser concluído
    loading_message.empty()
    st.markdown("""
    ## Importância de cada feature para o modelo
    É interessante perceber que o modelo utilizou variadas métricas para realizar essa predição, e não apenas os preços mais atuais.
    """)

with tab2:
    st.markdown("""
    # Previsão para 10 dias
    """)
    # Exibindo o texto introdutório
    st.markdown("""
    Realizou-se também um treinamento do modelo para que o mesmo efetue a previsão para os próximos 10 dias. As métricas do resultado e as features utilizadas são apresentadas a seguir:
    """)

    # Definindo os caminhos para as imagens
    image_path1 = os.path.join('Imagens', 'metricasd10.png')
    image_path2 = os.path.join('Imagens', 'featuresd10.png')

    # Carregando as imagens
    imagemetricas = Image.open(image_path1)
    imagefeatures = Image.open(image_path2)

    # Criando um layout de 3 colunas
    col1, col2 = st.columns([2, 1])

    # Colocando as imagens na coluna esquerda
    with col1:
        st.image(imagemetricas, caption='Métricas Observadas', use_column_width=True)
        st.image(imagefeatures, caption='Peso das Features', use_column_width=True)

    # Exibindo o texto de conclusão
    st.markdown("""
    Observa-se um erro que cresce de forma proporcional à quantidade de dias de previsão, o que é esperado, pois o modelo usa o output de uma previsão D+1 para input da previsão D+2, o que adiciona incertezas de forma sucessiva na previsão dos dias seguintes. Isso faz com que as previsões carreguem cada vez mais erros, e não sejam tão confiáveis para uma quantidade maior de dias.
    """)

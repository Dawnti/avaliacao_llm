import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials

# --- Configurações Iniciais ---
st.set_page_config(page_title="Avaliação de Planos de Cuidado", layout="centered")

# Cria pastas necessárias caso não existam
os.makedirs("dados", exist_ok=True)
os.makedirs("respostas", exist_ok=True)

# --- Sistema de Usuários e Senhas ---
# Para um ambiente real, senhas mais fortes são recomendadas.
USUARIOS = st.secrets["usuarios"]

# Inicializa o estado de login
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None

# --- Tela de Login ---
if not st.session_state.autenticado:
    st.title("🔒 Acesso Restrito")
    st.write("Por favor, insira suas credenciais para acessar os textos.")
    
    with st.form("login_form"):
        usuario_input = st.text_input("Usuário").lower().strip()
        senha_input = st.text_input("Senha", type="password")
        submit_login = st.form_submit_button("Entrar")
        
        if submit_login:
            if usuario_input in USUARIOS and USUARIOS[usuario_input] == senha_input:
                st.session_state.autenticado = True
                st.session_state.usuario_logado = usuario_input
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    
    # Interrompe a execução do resto do código se não estiver logado
    st.stop()

# ==========================================
# A PARTIR DAQUI, O USUÁRIO ESTÁ AUTENTICADO
# ==========================================
avaliador = st.session_state.usuario_logado

# --- Funções de Conexão com Google Sheets ---
@st.cache_resource
def conectar_google_sheets():
    """Configura e retorna o cliente do Google Sheets."""
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credenciais = Credentials.from_service_account_info(
        st.secrets["google_credentials"], 
        scopes=escopos
    )
    return gspread.authorize(credenciais)

def obter_planos_avaliados(avaliador):
    """Busca na planilha quais IDs de plano este avaliador já preencheu."""
    try:
        cliente = conectar_google_sheets()
        URL_DA_PLANILHA = st.secrets["planilha_url"]
        planilha = cliente.open_by_url(URL_DA_PLANILHA).worksheet("Resultados")
        
        # Pega todos os dados (lista de listas). A primeira lista é o cabeçalho.
        dados = planilha.get_all_values()
        
        if len(dados) <= 1: # Só tem o cabeçalho ou está vazia
            return []
            
        planos_avaliados = []
        # O cabeçalho está na linha 0. Os dados começam na linha 1.
        for linha in dados[1:]: 
            # Verifica se a linha tem colunas suficientes e se o avaliador (Coluna A, índice 0) bate
            if len(linha) > 1 and linha[0] == avaliador:
                try:
                     # O ID_Plano deve estar na Coluna B (índice 1)
                    planos_avaliados.append(int(linha[1]))
                except ValueError:
                    # Ignora se o ID na planilha não for um número válido
                    pass
        return planos_avaliados
    except Exception as e:
        st.error(f"Erro ao buscar histórico no Google Sheets: {e}")
        return []

# --- Carregamento de Dados ---
@st.cache_data
def carregar_planos():
    caminho_arquivo = "dados/planos.csv"
    if os.path.exists(caminho_arquivo):
        return pd.read_csv(caminho_arquivo)
    else:
        st.error("Arquivo dados/planos.csv não encontrado. Crie o arquivo com os dados.")
        st.stop()

df_planos = carregar_planos()

if 'avaliador_responsavel' not in df_planos.columns:
    st.error("O arquivo CSV precisa ter uma coluna chamada 'avaliador_responsavel'.")
    st.stop()

# 1. Filtra para mostrar apenas os planos alocados para este usuário
df_planos_usuario = df_planos[df_planos['avaliador_responsavel'] == avaliador]

# 2. Busca no Google Sheets o que ele já fez
planos_ja_feitos = obter_planos_avaliados(avaliador)

# 3. Filtra novamente: remove do DataFrame os planos que estão na lista de já feitos
# O símbolo ~ inverte a condição (mantém os que NÃO estão na lista)
df_pendentes = df_planos_usuario[~df_planos_usuario['id_plano'].isin(planos_ja_feitos)]

total_planos = len(df_pendentes)

if total_planos == 0:
    st.success(f"🎉 Fantástico, {avaliador.capitalize()}! Você já avaliou todos os planos designados para você.")
    if st.button("Sair da conta"):
        st.session_state.autenticado = False
        st.rerun()
    st.stop()

# --- Estado da Sessão (Paginação) ---
# Como agora filtramos os pendentes toda vez que a página carrega, o índice 
# pode sempre ser 0. O plano atual será sempre o primeiro da lista de pendentes.
indice = 0 
plano_atual = df_pendentes.iloc[indice]

# --- Cabeçalho e Progresso ---
col1, col2 = st.columns([8, 2])
with col1:
    st.title(f"Avaliação - {avaliador.capitalize()}")
with col2:
    if st.button("Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# Progresso: Quantos ele já fez vs o Total que ele tinha para fazer
total_original_do_usuario = len(df_planos_usuario)
quantidade_feita = len(planos_ja_feitos)
st.progress(quantidade_feita / total_original_do_usuario, text=f"Progresso: {quantidade_feita} de {total_original_do_usuario} concluídos.")
st.divider()

# --- Exibição do Texto ---
st.subheader("Considere o seguinte paciente e plano de cuidado:")
st.info(plano_atual["texto_plano"])
st.divider()

# --- Formulário de Avaliação ---
with st.form(key=f"form_{plano_atual['id_plano']}"):
    
    st.subheader("Parte 1: Avalie as afirmações")
    st.write("Levando em conta o quanto você concorda com elas:")
    
    opcoes_likert = [
        "1 - Discordo Totalmente", 
        "2 - Discordo", 
        "3 - Neutro", 
        "4 - Concordo", 
        "5 - Concordo Totalmente"
    ]
    
    q1 = st.radio("1. O plano contém uma grande quantidade de erros", opcoes_likert, index=2)
    q2 = st.radio("2. Fatores de risco importantes foram deixados de fora", opcoes_likert, index=2)
    q3 = st.radio("3. O plano está conciso e preciso", opcoes_likert, index=2)
    q4 = st.radio("4. A redação do texto foi escrita de forma clara e fácil de entender", opcoes_likert, index=2)
    
    st.write("---")
    q5 = st.select_slider(
        "5. Quão confiante você está de que esse plano foi escrito por um humano?", 
        options=["Nada Confiante", "Pouco Confiante", "Neutro", "Confiante", "Totalmente Confiante"], 
        value="Neutro"
    )

    st.subheader("Parte 2: Detalhamento")
    q6 = st.number_input("1. Quantos erros foram cometidos?", min_value=0, max_value=100, value=0, step=1)
    q7 = st.text_area("2. Quais foram os principais erros cometidos?")
    q8 = st.text_area("3. O que você mudaria nesse plano de cuidado?")

    st.divider()
    
    # Botão de envio
    btn_enviar = st.form_submit_button("Salvar e Próximo ➡️", type="primary")

# --- Lógica de Salvamento e Navegação ---
if btn_enviar:
    # 1. Obtém a conexão já cacheada
    cliente = conectar_google_sheets()
    
    # 2. Abre a planilha pelo link e seleciona a aba (Sheet1 ou Respostas)
    URL_DA_PLANILHA = st.secrets["planilha_url"]
    planilha = cliente.open_by_url(URL_DA_PLANILHA).worksheet("Página1") 
    
    # 3. Monta a linha com as respostas, convertendo números para string para evitar erros no gspread
    nova_linha = [
        avaliador,
        str(plano_atual["id_plano"]),
        q1, q2, q3, q4, q5, # Likert e Confiança
        str(q6), q7, q8     # Detalhamentos
    ]
    
    # 4. Envia a linha diretamente para o Google Sheets
    planilha.append_row(nova_linha)
    
    # Ao invés de incrementar um índice, nós simplesmente recarregamos a página.
    # Quando a página recarregar, a função 'obter_planos_avaliados' vai ler a planilha novamente,
    # vai ver que este ID acabou de ser salvo, e vai removê-lo da lista de pendentes!
    st.rerun()

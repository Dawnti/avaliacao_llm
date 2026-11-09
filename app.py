import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import gspread
from google.oauth2.service_account import Credentials

# --- Configurações Iniciais ---
st.set_page_config(page_title="Avaliação Comparativa de Planos", layout="centered")

# --- Sistema de Usuários e Senhas ---
USUARIOS = st.secrets["usuarios"]

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
    
    st.stop()

# ==========================================
# USUÁRIO AUTENTICADO
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

def obter_pacientes_avaliados(avaliador):
    """Busca na aba 'Resultados' quais pacientes este avaliador já concluiu."""
    try:
        cliente = conectar_google_sheets()
        URL_DA_PLANILHA = st.secrets["planilha_url"]
        
        sheet = cliente.open_by_url(URL_DA_PLANILHA)
        try:
            planilha_res = sheet.worksheet("Resultados")
        except gspread.exceptions.WorksheetNotFound:
            planilha_res = sheet.add_worksheet(title="Resultados", rows="1000", cols="25")
            planilha_res.append_row([
                "Avaliador", "Paciente", "Plano_A_Tipo", "Plano_B_Tipo",
                "A_q2", "A_q3", "A_q4", "A_q5", "A_q6", "A_q7", "A_q8",
                "B_q2", "B_q3", "B_q4", "B_q5", "B_q6", "B_q7", "B_q8",
                "Preferencia_Final"
            ])
            return []

        dados = planilha_res.get_all_values()
        if len(dados) <= 1:
            return []
            
        pacientes_avaliados = []
        for linha in dados[1:]: 
            if len(linha) > 1 and linha[0] == avaliador:
                pacientes_avaliados.append(str(linha[1]))
        return pacientes_avaliados
    except Exception as e:
        st.error(f"Erro ao buscar histórico no Google Sheets: {e}")
        return []

@st.cache_data(ttl=300)
def carregar_planos_sheets():
    """Carrega os dados diretamente da aba 'PlanosCuidado' do Google Sheets."""
    try:
        cliente = conectar_google_sheets()
        URL_DA_PLANILHA = st.secrets["planilha_url"]
        planilha = cliente.open_by_url(URL_DA_PLANILHA).worksheet("PlanosCuidado")
        dados = planilha.get_all_records()
        df = pd.DataFrame(dados)
        
        if 'paciente' in df.columns:
            df['paciente'] = df['paciente'].astype(str)
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a aba 'PlanosCuidado': {e}")
        st.stop()

def formatar_texto(texto):
    """Trata caracteres de escape e ajusta para a renderização em Markdown do Streamlit."""
    if not isinstance(texto, str):
        texto = str(texto)
        
    # 1. Padroniza quebras de linha do Windows (\r\n) para \n
    texto = texto.replace('\r\n', '\n')
    
    # 2. Caso o Sheets tenha enviado a string escapada literalmente ('\' + 'n')
    texto = texto.replace('\\n', '\n').replace('\\t', '\t')
    
    # 3. O SEGREDO DO STREAMLIT: 
    # Adiciona dois espaços antes do \n para forçar a quebra de linha no Markdown
    texto = texto.replace('\n', '  \n')
    
    # 4. Substitui tabulações por um espaçamento horizontal equivalente em HTML
    texto = texto.replace('\t', '&emsp;&emsp;')
    
    return texto

# --- Carregamento e Filtragem ---
df_planos = carregar_planos_sheets()

colunas_necessarias = ['paciente', 'plano_auto', 'plano_humano', 'avaliador', 'fatores']
for col in colunas_necessarias:
    if col not in df_planos.columns:
        st.error(f"A aba 'PlanosCuidado' precisa conter a coluna '{col}'. Colunas encontradas: {list(df_planos.columns)}")
        st.stop()

df_planos_usuario = df_planos[df_planos['avaliador'] == avaliador]
pacientes_ja_feitos = obter_pacientes_avaliados(avaliador)
df_pendentes = df_planos_usuario[~df_planos_usuario['paciente'].isin(pacientes_ja_feitos)]

total_original = len(df_planos_usuario)
quantidade_feita = len(pacientes_ja_feitos)

if len(df_pendentes) == 0:
    st.success(f"🎉 Fantástico, {avaliador.capitalize()}! Você já avaliou todos os pacientes designados para você.")
    if st.button("Sair da conta"):
        st.session_state.autenticado = False
        st.rerun()
    st.stop()

# Paciente atual e textos formatados
paciente_atual = df_pendentes.iloc[0]
id_paciente = str(paciente_atual["paciente"])
fatores_paciente = formatar_texto(paciente_atual["fatores"])

# --- Lógica de Sorteio de Ordem A/B ---
chave_ordem = f"ordem_{id_paciente}"
if chave_ordem not in st.session_state:
    opcoes = [
        ("humano", formatar_texto(paciente_atual["plano_humano"]), "auto", formatar_texto(paciente_atual["plano_auto"])),
        ("auto", formatar_texto(paciente_atual["plano_auto"]), "humano", formatar_texto(paciente_atual["plano_humano"]))
    ]
    st.session_state[chave_ordem] = random.choice(opcoes)

tipo_a, texto_a, tipo_b, texto_b = st.session_state[chave_ordem]

# --- Interface e Scroll ---
if st.session_state.get("rolar_topo", False):
    components.html(
        "<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>",
        height=0
    )
    st.session_state.rolar_topo = False

col1, col2 = st.columns([8, 2])
with col1:
    st.title(f"Avaliação - {avaliador.capitalize()}")
with col2:
    if st.button("Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

st.progress(
    quantidade_feita / total_original if total_original > 0 else 1.0, 
    text=f"Progresso: {quantidade_feita} de {total_original} pacientes concluídos."
)
st.divider()

#st.header(f"📋 Paciente ID: {id_paciente}")

st.subheader("Avaliações do Paciente (Fatores)")
st.info(fatores_paciente)
st.write("Abaixo você encontrará dois planos de cuidado elaborados para este paciente com base nos fatores acima. Avalie cada plano individualmente e, ao final, indique a sua preferência.")

opcoes_likert = [
    "1 - Discordo Totalmente", 
    "2 - Discordo", 
    "3 - Neutro", 
    "4 - Concordo", 
    "5 - Concordo Totalmente"
]

opcoes_erros = [
    "Nenhum erro",
    "Erros mínimos / pontuais",
    "Quantidade moderada de erros",
    "Muitos erros",
    "Quantidade crítica de erros"
]

# --- Formulário Principal ---
with st.form(key=f"form_paciente_{id_paciente}"):
    
    # ==========================================
    # PLANO A
    # ==========================================
    st.markdown("### 🔹 PLANO A")
    st.info(texto_a)
    
    st.markdown("**Parte 1: Avalie o Plano A**")
    a_q2 = st.radio("1. Fatores de risco importantes foram deixados de fora no Plano A", opcoes_likert, index=None, key=f"a_q2_{id_paciente}")
    a_q3 = st.radio("2. O Plano A está conciso e preciso", opcoes_likert, index=None, key=f"a_q3_{id_paciente}")
    a_q4 = st.radio("3. A redação do Plano A foi escrita de forma clara e fácil de entender", opcoes_likert, index=None, key=f"a_q4_{id_paciente}")
    
    a_q5 = st.select_slider(
        "4. Quão confiante você está de que o Plano A foi escrito por um humano?", 
        options=["Nada Confiante", "Pouco Confiante", "Neutro", "Confiante", "Totalmente Confiante"], 
        value="Neutro",
        key=f"a_q5_{id_paciente}"
    )

    st.markdown("**Parte 2: Detalhamento do Plano A**")
    a_q6 = st.select_slider(
        "1. Qual a quantidade/gravidade dos erros cometidos no Plano A?",
        options=opcoes_erros,
        value="Nenhum erro",
        key=f"a_q6_{id_paciente}"
    )
    a_q7 = st.text_area("2. Quais foram os principais erros cometidos no Plano A?", placeholder="Descreva aqui...", key=f"a_q7_{id_paciente}")
    a_q8 = st.text_area("3. O que você mudaria no Plano A?", placeholder="Descreva aqui...", key=f"a_q8_{id_paciente}")

    st.divider()

    # ==========================================
    # PLANO B
    # ==========================================
    st.markdown("### 🔸 PLANO B")
    st.info(texto_b)
    
    st.markdown("**Parte 1: Avalie o Plano B**")
    b_q2 = st.radio("1. Fatores de risco importantes foram deixados de fora no Plano B", opcoes_likert, index=None, key=f"b_q2_{id_paciente}")
    b_q3 = st.radio("2. O Plano B está conciso e preciso", opcoes_likert, index=None, key=f"b_q3_{id_paciente}")
    b_q4 = st.radio("3. A redação do Plano B foi escrita de forma clara e fácil de entender", opcoes_likert, index=None, key=f"b_q4_{id_paciente}")
    
    b_q5 = st.select_slider(
        "4. Quão confiante você está de que o Plano B foi escrito por um humano?", 
        options=["Nada Confiante", "Pouco Confiante", "Neutro", "Confiante", "Totalmente Confiante"], 
        value="Neutro",
        key=f"b_q5_{id_paciente}"
    )

    st.markdown("**Parte 2: Detalhamento do Plano B**")
    b_q6 = st.select_slider(
        "1. Qual a quantidade/gravidade dos erros cometidos no Plano B?",
        options=opcoes_erros,
        value="Nenhum erro",
        key=f"b_q6_{id_paciente}"
    )
    b_q7 = st.text_area("2. Quais foram os principais erros cometidos no Plano B?", placeholder="Descreva aqui...", key=f"b_q7_{id_paciente}")
    b_q8 = st.text_area("3. O que você mudaria no Plano B?", placeholder="Descreva aqui...", key=f"b_q8_{id_paciente}")

    st.divider()

    # ==========================================
    # PARTE COMPARATIVA
    # ==========================================
    st.subheader("Comparação Direta")
    preferencia = st.radio(
        "Qual dos dois planos você prefere no geral?",
        ["Prefiro o Plano A", "Prefiro o Plano B"],
        index=None,
        key=f"pref_{id_paciente}"
    )

    st.divider()
    btn_enviar = st.form_submit_button("Salvar e Próximo ➡️", type="primary")

# --- Lógica de Validação e Salvamento ---
if btn_enviar:
    a_incompleto = None in [a_q2, a_q3, a_q4] or not a_q7.strip() or not a_q8.strip()
    b_incompleto = None in [b_q2, b_q3, b_q4] or not b_q7.strip() or not b_q8.strip()
    pref_incompleta = preferencia is None

    if a_incompleto or b_incompleto or pref_incompleta:
        st.error("⚠️ Por favor, preencha todos os campos do Plano A, do Plano B e a pergunta de preferência antes de salvar.")
    else:
        cliente = conectar_google_sheets()
        URL_DA_PLANILHA = st.secrets["planilha_url"]
        planilha_res = cliente.open_by_url(URL_DA_PLANILHA).worksheet("Resultados")
        
        nova_linha = [
            avaliador,
            id_paciente,
            tipo_a,
            tipo_b,
            
            # Respostas Plano A
            a_q2, a_q3, a_q4, a_q5, str(a_q6), a_q7.strip(), a_q8.strip(),
            
            # Respostas Plano B
            b_q2, b_q3, b_q4, b_q5, str(b_q6), b_q7.strip(), b_q8.strip(),
            
            # Preferência
            preferencia
        ]
        
        planilha_res.append_row(nova_linha)
        
        if chave_ordem in st.session_state:
            del st.session_state[chave_ordem]
            
        st.session_state.rolar_topo = True
        st.rerun()

import streamlit as st
import pandas as pd
import random
from datetime import datetime
from supabase import create_client, Client

# ==============================
# CONFIGURACIÓN SUPABASE
# ==============================
SUPABASE_URL = "https://qkpdwzqxeweztwqbumxg.supabase.co"
SUPABASE_KEY = "sb_publishable_BIDqJoWRx2tF1amMejRUFA_XZZfxXgD"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# UTILIDADES
# ==============================
def parse_iso(dt_str):
    """Convierte strings ISO con o sin 'Z' a datetime."""
    if dt_str is None:
        return None
    try:
        # reemplaza Z por +00:00 para compatibilidad con fromisoformat
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        # fallback: intenta sin cambios
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

def generar_placa():
    """Genera una placa aleatoria tipo TRL1234"""
    return f"TRL{random.randint(1000,9999)}"

# ==============================
# SIMULACIÓN (Llegadas y Salidas)
# ==============================
def simular_llegada():
    """Simula la llegada de un trailer: crea trailer si no existe, asigna puerta libre y crea registro."""
    placa = generar_placa()

    # Verificar si existe trailer
    trailer = supabase.table("trailers").select("id_trailer").eq("placa", placa).execute()
    if not trailer.data:
        insert_trailer = supabase.table("trailers").insert({"placa": placa}).execute()
        # supabase devuelve lista; obtener id
        id_trailer = insert_trailer.data[0]["id_trailer"]
    else:
        id_trailer = trailer.data[0]["id_trailer"]

    # Buscar puerta libre (primer resultado)
    puerta = supabase.table("puertas").select("id_puerta, numero_puerta").eq("estado", "LIBRE").limit(1).execute()
    if puerta.data:
        id_puerta = puerta.data[0]["id_puerta"]
        hora_entrada = datetime.utcnow().isoformat() + "Z"  # usar UTC y marcar con Z

        # Insertar registro
        supabase.table("registros").insert({
            "id_trailer": id_trailer,
            "id_puerta": id_puerta,
            "hora_entrada": hora_entrada
        }).execute()

        # Actualizar puerta a OCUPADA
        supabase.table("puertas").update({"estado": "OCUPADA"}).eq("id_puerta", id_puerta).execute()
        return f"Llegada: trailer {placa} -> puerta {id_puerta}"
    else:
        return "Llegada: no hay puertas libres"

def simular_salida():
    """Simula la salida de un trailer: cierra el registro más antiguo abierto y libera la puerta."""
    # Seleccionar un registro con hora_salida NULL (es decir abierto)
    registro = supabase.table("registros").select("id_registro, id_puerta, hora_entrada").is_("hora_salida", None).limit(1).execute()
    if registro.data:
        id_registro = registro.data[0]["id_registro"]
        id_puerta = registro.data[0]["id_puerta"]
        hora_entrada_str = registro.data[0].get("hora_entrada")
        hora_entrada = parse_iso(hora_entrada_str) or datetime.utcnow()

        hora_salida = datetime.utcnow()
        tiempo = hora_salida - hora_entrada

        # Actualizar registro: hora_salida y tiempo_estancia (texto ISO del intervalo)
        supabase.table("registros").update({
            "hora_salida": hora_salida.isoformat() + "Z",
            "tiempo_estancia": str(tiempo)
        }).eq("id_registro", id_registro).execute()

        # Liberar la puerta
        supabase.table("puertas").update({"estado": "LIBRE"}).eq("id_puerta", id_puerta).execute()
        return f"Salida: registro {id_registro} -> puerta {id_puerta} liberada"
    else:
        return "Salida: no hay trailers en puertas"

def ejecutar_simulacion_automatica(max_llegadas=3, max_salidas=3):
    """Ejecuta un lote aleatorio de llegadas y salidas en una sola pasada.
       Devuelve lista de mensajes con lo ocurrido."""
    msgs = []
    # números aleatorios de eventos (puedes ajustar aquí)
    n_llegadas = random.randint(0, max_llegadas)
    n_salidas = random.randint(0, max_salidas)

    # Prioridad: alternar llegada/salida para mayor realismo
    for _ in range(max(n_llegadas, n_salidas)):
        if _ < n_llegadas:
            msgs.append(simular_llegada())
        if _ < n_salidas:
            msgs.append(simular_salida())

    return msgs

# ==============================
# STREAMLIT - INTERFAZ
# ==============================
st.set_page_config(page_title="Sistema Control - Estación de Trailers", layout="wide")
st.title("CamBus")

# Inicializar session_state
if "user" not in st.session_state:
    st.session_state.user = None
    st.session_state.rol = None

# ------------------------------
# LOGIN SIMPLE
# ------------------------------
if st.session_state.user is None:
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        response = supabase.table("usuarios").select("rol").eq("username", username).eq("password", password).execute()
        if response.data:
            st.session_state.user = username
            st.session_state.rol = response.data[0]["rol"]
            st.success("Login correcto")
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()  # detener render hasta login
else:
    st.sidebar.write(f"Usuario: {st.session_state.user}")
    st.sidebar.write(f"Rol: {st.session_state.rol}")

    if st.sidebar.button("Cerrar sesión"):
        st.session_state.user = None
        st.session_state.rol = None
        st.rerun()

# ==============================
# EJECUTAR SIMULACIÓN AUTOMÁTICA (si es ADMIN)
# ==============================
sim_msgs = []
if st.session_state.rol == "ADMIN":
    st.header("⚙ Simulación Automática (ejecutada en cada carga de la página)")
    try:
        sim_msgs = ejecutar_simulacion_automatica(max_llegadas=3, max_salidas=3)
    except Exception as e:
        st.error(f"Error al ejecutar la simulación: {e}")

    # Mostrar resultados de la simulación
    if sim_msgs:
        for m in sim_msgs:
            st.write("·", m)
    else:
        st.write("No se generaron eventos en esta ejecución.")

# ==============================
# MOSTRAR ESTADO DE PUERTAS
# ==============================
st.subheader("📊 Estado de Puertas")
puertas = supabase.table("puertas").select("id_puerta, numero_puerta, estado").order("numero_puerta").execute()
df_puertas = pd.DataFrame(puertas.data)
if df_puertas.empty:
    st.write("No hay datos de puertas.")
else:
    # mostrar como dataframe y también un tablero simple de colores (texto)
    st.dataframe(df_puertas)

    # tablero compacto: 10 columnas x 10 filas
    st.markdown("**Tablero (OCUPADA / LIBRE)**")
    cols = st.columns(10)
    # Crear lista ordenada por numero_puerta
    for i, row in df_puertas.sort_values("numero_puerta").reset_index(drop=True).iterrows():
        col_idx = i % 10
        with cols[col_idx]:
            estado = row["estado"]
            num = int(row["numero_puerta"])
            if estado == "OCUPADA":
                st.markdown(f"<div style='background:#ffcccc;padding:6px;border-radius:6px'>Puerta {num}<br><b>OCUPADA</b></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background:#ccffcc;padding:6px;border-radius:6px'>Puerta {num}<br><b>LIBRE</b></div>", unsafe_allow_html=True)

# ==============================
# CRUD TRAILERS
# ==============================
st.divider()
st.header("🚛 Gestión de Trailers")

# Obtener trailers
trailers_resp = supabase.table("trailers").select("*").order("id_trailer").execute()
df_trailers = pd.DataFrame(trailers_resp.data)

# -------------------------
# MOSTRAR TABLA
# -------------------------
if df_trailers.empty:
    st.write("No hay trailers registrados.")
else:
    st.dataframe(df_trailers)

# -------------------------
# SOLO ADMIN PUEDE MODIFICAR
# -------------------------
if st.session_state.rol == "ADMIN":

    st.subheader("➕ Agregar Nuevo Trailer")
    nueva_placa = st.text_input("Placa nueva")

    if st.button("Crear Trailer"):
        if nueva_placa.strip() == "":
            st.warning("La placa no puede estar vacía.")
        else:
            try:
                supabase.table("trailers").insert({
                    "placa": nueva_placa.strip().upper()
                }).execute()
                st.success("Trailer creado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al crear trailer: {e}")

    st.divider()
    st.subheader("✏ Editar Trailer")

    if not df_trailers.empty:
        trailer_edit = st.selectbox(
            "Selecciona trailer a editar",
            df_trailers["id_trailer"],
            format_func=lambda x: f"ID {x} - {df_trailers[df_trailers['id_trailer']==x]['placa'].values[0]}"
        )

        nueva_placa_edit = st.text_input("Nueva placa")

        if st.button("Actualizar Trailer"):
            if nueva_placa_edit.strip() == "":
                st.warning("La placa no puede estar vacía.")
            else:
                try:
                    supabase.table("trailers").update({
                        "placa": nueva_placa_edit.strip().upper()
                    }).eq("id_trailer", trailer_edit).execute()
                    st.success("Trailer actualizado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")

    st.divider()
    st.subheader("❌ Eliminar Trailer")

    if not df_trailers.empty:
        trailer_delete = st.selectbox(
            "Selecciona trailer a eliminar",
            df_trailers["id_trailer"],
            key="delete_trailer",
            format_func=lambda x: f"ID {x} - {df_trailers[df_trailers['id_trailer']==x]['placa'].values[0]}"
        )

        if st.button("Eliminar Trailer"):
            try:
                # Verificar si tiene registros activos
                registros_activos = supabase.table("registros") \
                    .select("id_registro") \
                    .eq("id_trailer", trailer_delete) \
                    .is_("hora_salida", None) \
                    .execute()

                if registros_activos.data:
                    st.error("No se puede eliminar: el trailer está actualmente en una puerta.")
                else:
                    supabase.table("trailers") \
                        .delete() \
                        .eq("id_trailer", trailer_delete) \
                        .execute()

                    st.success("Trailer eliminado correctamente.")
                    st.rerun()

            except Exception as e:
                st.error(f"Error al eliminar: {e}")

else:
    st.info("Usuario con permisos de solo lectura.")

# ==============================
# HISTORIAL DE REGISTROS
# ==============================
st.subheader("📜 Historial de Registros (últimos 200)")

# Traer registros con join a trailers y puertas usando el nombre de relaciones que tengas
# En Supabase PostgREST la sintaxis es: select("*, trailers(placa), puertas(numero_puerta)")
historial = supabase.table("registros").select("""
    id_registro,
    hora_entrada,
    hora_salida,
    tiempo_estancia,
    trailers ( placa ),
    puertas ( numero_puerta )
""").order("hora_entrada", desc=True).limit(200).execute()

registros = []
if historial.data:
    for row in historial.data:
        placa = None
        numero_puerta = None
        # Manejar structure del row (puede venir como dict)
        if row.get("trailers"):
            placa = row["trailers"].get("placa")
        if row.get("puertas"):
            numero_puerta = row["puertas"].get("numero_puerta")
        registros.append({
            "id_registro": row.get("id_registro"),
            "placa": placa,
            "numero_puerta": numero_puerta,
            "hora_entrada": row.get("hora_entrada"),
            "hora_salida": row.get("hora_salida"),
            "tiempo_estancia": row.get("tiempo_estancia")
        })

df_historial = pd.DataFrame(registros)
if df_historial.empty:
    st.write("No hay registros aún.")
else:
    st.dataframe(df_historial)

# ==============================
# ESTADÍSTICAS SIMPLES
# ==============================
st.subheader("📈 Estadísticas rápidas")
try:
    total_puertas = len(df_puertas)
    ocupadas = len(df_puertas[df_puertas["estado"] == "OCUPADA"]) if not df_puertas.empty else 0
    porcentaje = (ocupadas / total_puertas * 100) if total_puertas else 0
    st.write(f"Puertas totales: **{total_puertas}** — Ocupadas: **{ocupadas}** ({porcentaje:.1f}%)")
except Exception:
    pass
import streamlit as st
import pandas as pd
import random
from datetime import datetime
from supabase import create_client, Client

# ... (Mantenemos tu configuración de SUPABASE_URL y KEY igual) ...

# ==============================
# SIMULACIÓN MEJORADA
# ==============================
def simular_llegada():
    """Busca puertas libres y elige una al azar, no la primera."""
    # 1. Obtener todas las placas existentes para elegir una al azar o crear nueva
    res_trailers = supabase.table("trailers").select("id_trailer", "placa").execute()
    if res_trailers.data:
        trailer_random = random.choice(res_trailers.data)
        id_trailer = trailer_random["id_trailer"]
        placa = trailer_random["placa"]
    else:
        placa = generar_placa()
        insert_t = supabase.table("trailers").insert({"placa": placa}).execute()
        id_trailer = insert_t.data[0]["id_trailer"]

    # 2. Buscar TODAS las puertas libres
    puertas_libres = supabase.table("puertas").select("id_puerta").eq("estado", "LIBRE").execute()
    
    if puertas_libres.data:
        # ¡AQUÍ ESTÁ EL CAMBIO! Elegimos una puerta al azar de la lista de libres
        puerta_elegida = random.choice(puertas_libres.data)
        id_p = puerta_elegida["id_puerta"]
        
        hora_entrada = datetime.utcnow().isoformat() + "Z"
        supabase.table("registros").insert({
            "id_trailer": id_trailer,
            "id_puerta": id_p,
            "hora_entrada": hora_entrada
        }).execute()

        supabase.table("puertas").update({"estado": "OCUPADA"}).eq("id_puerta", id_p).execute()
        return f"Llegada: {placa} -> Puerta {id_p} (Aleatoria)"
    return "Llegada: Patio lleno."

# ==============================
# CRUD DE TRAILERS (Nueva Función)
# ==============================
def seccion_crud_trailers():
    st.header("🚛 Gestión de Flota (CRUD)")
    
    tab1, tab2, tab3 = st.tabs(["Listar y Editar", "Añadir Nuevo", "Eliminar"])

    # --- LISTAR Y EDITAR ---
    with tab1:
        res = supabase.table("trailers").select("*").order("id_trailer").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            st.write("Selecciona un trailer para editar su placa:")
            selected_id = st.selectbox("ID del Trailer", df["id_trailer"])
            nueva_placa = st.text_input("Nueva Placa", key="edit_placa")
            if st.button("Actualizar Placa"):
                supabase.table("trailers").update({"placa": nueva_placa}).eq("id_trailer", selected_id).execute()
                st.success("¡Placa actualizada!")
                st.rerun()
            st.dataframe(df, use_container_width=True)

    # --- AÑADIR ---
    with tab2:
        nueva_p = st.text_input("Placa del nuevo trailer (ej. MX-ABC-1234)")
        if st.button("Guardar Trailer"):
            try:
                supabase.table("trailers").insert({"placa": nueva_p}).execute()
                st.success(f"Trailer {nueva_p} registrado.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: Tal vez la placa ya existe.")

    # --- ELIMINAR ---
    with tab3:
        id_del = st.number_input("ID a eliminar", step=1)
        if st.button("Confirmar Eliminación", type="primary"):
            # Nota: Fallará si el trailer tiene registros (por integridad referencial)
            supabase.table("trailers").delete().eq("id_trailer", id_del).execute()
            st.warning(f"Trailer {id_del} eliminado.")
            st.rerun()

# ==============================
# INTERFAZ PRINCIPAL (MODIFICADA)
# ==============================
# ... (Después del login) ...

menu = st.sidebar.selectbox("Ir a:", ["Dashboard", "Gestión de Trailers", "Historial"])

if menu == "Dashboard":
    # Aquí pones tu lógica de simulación y el tablero de puertas 10x10
    if st.session_state.rol == "ADMIN":
        if st.button("🚀 Ejecutar Ciclo de Simulación"):
            msgs = ejecutar_simulacion_automatica()
            for m in msgs: st.toast(m) # Toast es más limpio que escribir en pantalla
    
    # ... (Aquí va tu código de las cajitas de colores de las puertas) ...

elif menu == "Gestión de Trailers":
    seccion_crud_trailers()

elif menu == "Historial":
    st.subheader("📜 Historial de Registros")
    # ... (Aquí va tu código de la tabla de registros) ...

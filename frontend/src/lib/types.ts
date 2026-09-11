export type Pierna = "derecha" | "izquierda";

export type FileStatus = "pending" | "processing" | "done" | "error";

export type EquationSettings = {
  id: number;
  alpha: number;
  umbral_balanceo_deg_s: number;
  umbral_tc_deg_s: number;
  distancia_min_balanceo_s: number;
  distancia_min_minimos_s: number;
  metodo_deteccion_lado: "pierna" | "auto";
};

export type FileRow = {
  id: string;
  uploaded_by: string;
  nombre_original: string;
  storage_path: string;
  pierna: Pierna;
  status: FileStatus;
  error_message: string | null;
  created_at: string;
};

// Forma de la respuesta de POST /analyze del microservicio (ver microservice/analysis.py).
export type AnalysisServiceResponse = {
  parametros: {
    alpha: number;
    umbral_balanceo_deg_s: number;
    umbral_tc_deg_s: number;
    distancia_min_balanceo_s: number;
    distancia_min_minimos_s: number;
  };
  frecuencia_muestreo_hz: number;
  deteccion_lado: {
    metodo: string;
    pierna_declarada: Pierna;
    inversion_aplicada: boolean;
  };
  eventos: {
    tiempo_normalizado_s: number[];
    senal_filtrada: number[];
    indices_balanceo: number[];
    indices_contacto_inicial: number[];
    indices_contacto_terminal: number[];
  };
  metricas: {
    duracion_ciclo_s: number[];
    duracion_promedio_ciclo_s: number | null;
    tiempos_apoyo_s: number[];
    tiempo_promedio_apoyo_s: number | null;
    tiempos_balanceo_s: number[];
    tiempo_promedio_balanceo_s: number | null;
    cadencia_promedio_pasos_min: number | null;
  };
};

export type AnalysisResultRow = {
  id: string;
  file_id: string;
  parametros_usados: AnalysisServiceResponse["parametros"];
  deteccion_lado: AnalysisServiceResponse["deteccion_lado"];
  frecuencia_muestreo_hz: number | null;
  duracion_ciclo_promedio_s: number | null;
  tiempo_apoyo_promedio_s: number | null;
  tiempo_balanceo_promedio_s: number | null;
  cadencia_promedio_pasos_min: number | null;
  raw_json: AnalysisServiceResponse;
  created_at: string;
  created_by: string;
};

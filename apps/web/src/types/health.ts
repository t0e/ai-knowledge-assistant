export interface ServiceComponentHealth {
  status: string;
  connected: boolean;
  error?: string | null;
}

export interface DatabaseHealth extends ServiceComponentHealth {
  pgvector_installed: boolean;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  project_name: string;
  version: string;
  environment: string;
  timestamp: string;
  database: DatabaseHealth;
  redis: ServiceComponentHealth;
}

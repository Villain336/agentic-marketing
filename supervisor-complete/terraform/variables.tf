variable "project_name" {
  description = "Name of the project, used as prefix for all resources"
  type        = string
  default     = "supervisor"
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be 'staging' or 'production'."
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "domain" {
  description = "Domain name for the application (e.g., supervisor.example.com)"
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS on the ALB"
  type        = string
}

# ---------- Networking ----------

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ---------- ECS Backend ----------

variable "backend_cpu" {
  description = "CPU units for the backend task (1 vCPU = 1024)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Memory (MiB) for the backend task"
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Desired number of backend task instances"
  type        = number
  default     = 2
}

# ---------- ECS Webapp ----------

variable "webapp_cpu" {
  description = "CPU units for the webapp task (1 vCPU = 1024)"
  type        = number
  default     = 256
}

variable "webapp_memory" {
  description = "Memory (MiB) for the webapp task"
  type        = number
  default     = 512
}

variable "webapp_desired_count" {
  description = "Desired number of webapp task instances"
  type        = number
  default     = 2
}

# ---------- RDS (Optional) ----------

variable "enable_rds" {
  description = "Whether to create an RDS PostgreSQL instance"
  type        = bool
  default     = false
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "supervisor"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "supervisor_admin"
  sensitive   = true
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  default     = ""
  sensitive   = true
}

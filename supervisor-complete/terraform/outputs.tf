output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Route 53 zone ID of the ALB (for alias records)"
  value       = aws_lb.main.zone_id
}

output "ecr_backend_repository_url" {
  description = "ECR repository URL for the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_webapp_repository_url" {
  description = "ECR repository URL for the webapp image"
  value       = aws_ecr_repository.webapp.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "backend_service_name" {
  description = "Name of the backend ECS service"
  value       = aws_ecs_service.backend.name
}

output "webapp_service_name" {
  description = "Name of the webapp ECS service"
  value       = aws_ecs_service.webapp.name
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "rds_endpoint" {
  description = "RDS instance endpoint (if enabled)"
  value       = var.enable_rds ? aws_db_instance.main[0].endpoint : null
}

# ---------- Disaster Recovery Outputs ----------

output "dr_health_check_id" {
  description = "Route 53 health check ID for primary region"
  value       = var.enable_dr && var.route53_zone_id != "" ? aws_route53_health_check.primary[0].id : null
}

output "rds_replica_endpoint" {
  description = "RDS read replica endpoint (if enabled)"
  value       = var.enable_rds && var.enable_rds_read_replica ? aws_db_instance.replica[0].endpoint : null
}

output "dr_state_bucket" {
  description = "S3 bucket for DR state backup"
  value       = var.enable_dr ? aws_s3_bucket.dr_state_backup[0].id : null
}

output "api_url" {
  value = "https://${var.api_domain}"
}

output "alb_dns_name" {
  description = "Point api_domain here when Route 53 does not hold the zone"
  value       = aws_lb.api.dns_name
}

output "web_url" {
  value = local.web_origin
}

output "cloudfront_domain" {
  description = "Point web_domain here when Route 53 does not hold the zone"
  value       = aws_cloudfront_distribution.web.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.web.id
}

output "web_bucket" {
  value = aws_s3_bucket.web.bucket
}

output "documents_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "private_subnet_ids" {
  description = "For the one-off migration task"
  value       = aws_subnet.private[*].id
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "deploy_role_arn" {
  description = "AWS_ROLE_ARN of the GitHub environment"
  value       = aws_iam_role.deploy.arn
}

output "alarm_topic_arn" {
  value = aws_sns_topic.alarms.arn
}

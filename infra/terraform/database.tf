resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 5
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "qlda"
  username = "qlda"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  # SPEC 4.17: automatic backups kept 7 days
  backup_retention_period      = 7
  backup_window                = "17:00-18:00" # 00:00-01:00 in Vietnam
  maintenance_window           = "sun:18:00-sun:19:00"
  copy_tags_to_snapshot        = true
  auto_minor_version_upgrade   = true
  deletion_protection          = local.prod
  skip_final_snapshot          = !local.prod
  final_snapshot_identifier    = local.prod ? "${local.name}-final" : null
  performance_insights_enabled = false
}

# 🔗 **Terraform: Cross-Account Networking for Databricks ↔ RDS PostgreSQL**

## 🏗️ **Architecture Overview**
- **Databricks Workspace** (Account A): Runs in a **VPC** with clusters/SQL warehouses.
- **RDS PostgreSQL** (Account B): In a **private subnet** within another **VPC**.
- **Challenge**: Secure, private connectivity **without public internet**.
- **Recommended Solution**: **AWS PrivateLink** (Interface Endpoints)
  - ✅ No VPC Peering required
  - ✅ No route table updates
  - ✅ Encrypted, private traffic
  - ✅ Cross-account native support
  - ✅ Databricks officially recommends for RDS access
- **Alternative**: **VPC Peering** (if PrivateLink not feasible)
- **Assumptions**:
  - AWS provider
  - Terraform v1.5+
  - Databricks workspace already deployed (use `databricks` provider)
  - RDS PostgreSQL already exists

---

## 🎯 **Solution 1: AWS PrivateLink (Recommended)**

### **Account B: RDS Provider (Endpoint Service)**
Create **NLB → VPC Endpoint Service** in front of RDS.

#### **Terraform Code: `rds-account/main.tf`**
```hcl
provider "aws" {
  alias  = "rds"
  region = "us-east-1"
}

# Existing RDS PostgreSQL
module "rds" {
  source = "terraform-aws-modules/rds/aws"

  identifier           = "databricks-postgres"
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  username             = "admin"
  password             = "SecurePass123!"
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name = aws_db_subnet_group.main.name
  skip_final_snapshot  = true
}

# NLB in front of RDS (PrivateLink requires NLB)
resource "aws_lb" "rds_nlb" {
  name               = "rds-postgres-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = aws_db_subnet_group.main.subnet_ids

  enable_deletion_protection = false
}

resource "aws_lb_target_group" "rds_tg" {
  name     = "rds-postgres-tg"
  port     = 5432
  protocol = "TCP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    protocol = "TCP"
    port     = "5432"
  }
}

resource "aws_lb_target_group_attachment" "rds_attachment" {
  target_group_arn = aws_lb_target_group.rds_tg.arn
  target_id        = module.rds.this_db_instance.id
  port             = 5432
}

resource "aws_lb_listener" "rds_listener" {
  load_balancer_arn = aws_lb.rds_nlb.arn
  port              = "5432"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.rds_tg.arn
  }
}

# VPC Endpoint Service
resource "aws_vpc_endpoint_service" "rds_service" {
  acceptance_required        = false
  network_load_balancer_arns = [aws_lb.rds_nlb.arn]

  allowed_principals = ["arn:aws:iam::${data.aws_caller_identity.databricks.account_id}:root"]

  tags = {
    Name = "databricks-rds-postgres"
  }
}

# RDS Security Group: Allow INGRESS from PrivateLink Endpoint SG
resource "aws_security_group" "rds_sg" {
  name_prefix
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

```
## 🎯 **Solution 2: VPC Peering (Alternative)**
### Account A (Requester)
```hcl
resource "aws_vpc_peering_connection" "cross_account" {
  peer_vpc_id   = data.terraform_remote_state.rds.outputs.vpc_id
  vpc_id        = data.databricks_aws_workspace_conf.this.root_vpc_id
  peer_owner_id = data.aws_caller_identity.rds.account_id
  auto_accept   = false

  accepter {
    allow_remote_vpc_dns_resolution = true
  }

  requester {
    allow_remote_vpc_dns_resolution = true
  }
}

data "aws_caller_identity" "rds" {
  provider = aws.rds
}
```
### Account B (Accepter)
```hcl
resource "aws_vpc_peering_connection_accepter" "peer" {
  vpc_peering_connection_id = data.terraform_remote_state.databricks.outputs.peering_id
  auto_accept               = true
}
```
### Route Tables (Both Accounts)
```hcl
# Add routes for peering (Account A)
resource "aws_route" "peer_to_rds" {
  route_table_id         = data.databricks_aws_workspace_conf.this.private_route_table_ids
  destination_cidr_block = data.terraform_remote_state.rds.outputs.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.cross_account.id
}

# Add routes for peering (Account B)
resource "aws_route" "peer_to_databricks" {
  route_table_id         = module.vpc.private_route_table_ids
  destination_cidr_block = data.terraform_remote_state.databricks.outputs.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection_accepter.peer.vpc_peering_connection_id
}
```
### Security Groups (Peering-Specific Ingress/Egress)
```hcl
# RDS SG (Account B): INGRESS from Databricks SG
resource "aws_security_group_rule" "rds_ingress_from_databricks" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds_sg.id
  source_security_group_id = data.terraform_remote_state.databricks.outputs.databricks_sg_id
}

# Databricks SG (Account A): EGRESS to RDS SG
resource "aws_security_group_rule" "databricks_egress_to_rds" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.databricks_sg.id
  source_security_group_id = data.terraform_remote_state.rds.outputs.rds_sg_id
}
```
### Outputs for Peering: databricks-account/outputs.tf (Add to Existing) 
```hcl
output "peering_id" {
  value = aws_vpc_peering_connection.cross_account.id
}

output "vpc_cidr" {
  value = data.databricks_aws_workspace_conf.this.root_vpc_cidr
}
```
### Outputs for Peering: rds-account/outputs.tf (Add to Existing)
```hcl
output "vpc_id" {
  value = module.vpc.vpc_id
}
```
## 🛡️ Ingress/Egress Summary Table
```hcl

```


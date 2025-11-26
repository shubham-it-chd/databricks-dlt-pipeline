📜 Conversation Timeline
Initial Query (User)
terraform ingress egress databricks and rds prostgress both are in different account
Response 1: Full Terraform Guide (Initial Draft)
(This was the first comprehensive response, focusing on PrivateLink as recommended, with VPC Peering as alternative. It included code snippets, tables, and deployment steps.)
🏗️ Architecture Overview

Databricks Workspace (Account A): Runs in a VPC with clusters/SQL warehouses.
RDS PostgreSQL (Account B): In a private subnet within another VPC.
Challenge: Secure, private connectivity without public internet.
Recommended Solution: AWS PrivateLink (Interface Endpoints)
✅ No VPC Peering required
✅ No route table updates
✅ Encrypted, private traffic
✅ Cross-account native support
✅ Databricks officially recommends for RDS access

Alternative: VPC Peering (if PrivateLink not feasible)
Assumptions:
AWS provider
Terraform v1.5+
Databricks workspace already deployed (use databricks provider)
RDS PostgreSQL already exists


🎯 Solution 1: AWS PrivateLink (Recommended)
Account B: RDS Provider (Endpoint Service)
Create NLB → VPC Endpoint Service in front of RDS.
Terraform Code: rds-account/main.tf
hclprovider "aws" {
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
  name_prefix = "rds-databricks-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [data.terraform_remote_state.databricks.outputs.endpoint_sg_id]  # Cross-account remote state
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "terraform_remote_state" "databricks" {
  backend = "s3"
  config = {
    bucket = "databricks-tf-state"
    key    = "vpc/terraform.tfstate"
    region = "us-east-1"
  }
}
Outputs: rds-account/outputs.tf
hcloutput "endpoint_service_arn" {
  value = aws_vpc_endpoint_service.rds_service.arn
}
Account A: Databricks Consumer (Interface Endpoint)
Terraform Code: databricks-account/main.tf
hclprovider "aws" {
  alias  = "databricks"
  region = "us-east-1"
}

# Databricks VPC (assumes workspace deployed)
data "databricks_aws_workspace_conf" "this" {
  workspace_url = "https://your-workspace.cloud.databricks.com"
}

# Interface VPC Endpoint to RDS Service
resource "aws_vpc_endpoint" "rds_endpoint" {
  vpc_id              = data.databricks_aws_workspace_conf.this.root_vpc_id
  service_name        = data.terraform_remote_state.rds.outputs.endpoint_service_arn  # Cross-account
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.databricks_aws_workspace_conf.this.private_subnet_ids
  security_group_ids  = [aws_security_group.endpoint_sg.id]
  private_dns_enabled = true

  tags = {
    Name = "databricks-rds-postgres"
  }
}

# Endpoint Security Group: Allow EGRESS to RDS
resource "aws_security_group" "endpoint_sg" {
  name_prefix = "endpoint-databricks-"
  vpc_id      = data.databricks_aws_workspace_conf.this.root_vpc_id

  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [data.terraform_remote_state.rds.outputs.rds_sg_id]
  }
}

# Databricks Cluster Security Group: Allow INGRESS/EGRESS (if custom)
resource "aws_security_group" "databricks_sg" {
  name_prefix = "databricks-cluster-"
  vpc_id      = data.databricks_aws_workspace_conf.this.root_vpc_id

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.terraform_remote_state.rds.outputs.vpc_cidr]  # Or use SG reference
  }
}
Outputs: databricks-account/outputs.tf
hcloutput "endpoint_sg_id" {
  value = aws_security_group.endpoint_sg.id
}
🔄 Solution 2: VPC Peering (Alternative)
Account A (Requester)
hclresource "aws_vpc_peering_connection" "cross_account" {
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
Account B (Accepter)
hclresource "aws_vpc_peering_connection_accepter" "peer" {
  vpc_peering_connection_id = data.terraform_remote_state.databricks.outputs.peering_id
  auto_accept               = true
}
Route Tables (Both Accounts)
hcl# Add routes for peering
resource "aws_route" "peer" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = data.terraform_remote_state.[other].vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.cross_account.id
}
Security Groups (Peering-Specific Ingress/Egress)
hcl# RDS SG (Account B): INGRESS from Databricks SG
ingress {
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = data.terraform_remote_state.databricks.outputs.databricks_sg_id
}

# Databricks SG (Account A): EGRESS to RDS SG
egress {
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = data.terraform_remote_state.rds.outputs.rds_sg_id
}
🛡️ Ingress/Egress Summary Table

























ComponentIngress (Inbound)Egress (Outbound)RDS PostgreSQL✅ Port 5432 from Endpoint SG or Databricks SG✅ All outbound (0.0.0.0/0)PrivateLink EndpointN/A (managed by AWS)✅ Port 5432 to RDS SGDatabricks ClustersN/A✅ Port 5432 to RDS VPC CIDR or RDS SG
🚀 Deployment Steps

Initialize Remote State:Bashterraform init -backend-config="bucket=your-state-bucket"
Deploy RDS Account First → Output endpoint_service_arn
Deploy Databricks Account → Reference RDS state
Test Connectivity:SQL-- In Databricks Notebook
%sql SELECT version();
jdbc:postgresql://vpce-xxx.rds-postgres.your-service.vpce-svc-xxx.us-east-1.vpce.amazonaws.com:5432/yourdb
Apply: terraform apply in both accounts.

⚠️ Best Practices

Remote State: Use S3 + DynamoDB for cross-account references.
Encryption: Enable RDS encryption & PrivateLink DNS.
Monitoring: CloudWatch Logs for RDS & Databricks.
Cost: PrivateLink ~$0.01/GB + NLB costs.
Docs: Databricks AWS Networking

Need full repo or Azure equivalent? Let me know! 🚀
## # 🔗 **Amazon VPC Lattice: Secure Cross-Account Networking for Databricks ↔ RDS PostgreSQL**

## 🏗️ **Overview**
Building on our previous discussion about cross-account connectivity between **Databricks** (Account A) and **RDS PostgreSQL** (Account B), **Amazon VPC Lattice** is AWS's fully managed application networking service that simplifies secure, private service-to-service communication. It's a modern alternative to PrivateLink or VPC Peering, especially for TCP-based resources like RDS.

### Why VPC Lattice? ✅
- **Cross-Account Native**: Share via **AWS Resource Access Manager (RAM)** – no complex peering or endpoint services.
- **TCP Support**: Ideal for databases (e.g., RDS on port 5432) with automatic service discovery, traffic routing, and monitoring.
- **Managed Everything**: Handles east-west traffic across VPCs, accounts, EC2, containers (Databricks clusters), and serverless – no sidecars or manual configs.
- **Security**: IAM auth policies (for HTTP/GRPC), network policies, and encryption in transit.
- **Cost**: ~$0.01/GB processed + $0.025/hour per service network (as of 2025).
- **Limitations**: TCP doesn't support IAM auth (use SGs); best for L7 (HTTP/HTTPS) but works for L4 TCP.

**Assumptions** (Same as Before):
- AWS provider, Terraform v1.5+.
- Databricks workspace deployed in VPC (Account A).
- RDS PostgreSQL in private subnets (Account B).
- Centralized **Networking Account (C)** for Service Network (optional but recommended for multi-account).

**High-Level Flow**:
1. **Networking Account (C)**: Create & share **Service Network** via RAM.
2. **RDS Account (B)**: Create **Resource Gateway** & **Resource Configuration** (points to RDS ARN), associate to Service Network.
3. **Databricks Account (A)**: Create **VPC Endpoint** to shared Service Network for private access.

---

## 🎯 **Terraform Setup Guide**

Use the official **AWS VPC Lattice Terraform Module** for simplicity: [aws-ia/amazon-vpc-lattice-module](https://registry.terraform.io/modules/aws-ia/amazon-vpc-lattice-module/aws/latest).

### **Prerequisites**
- Enable VPC DNS support/hostnames in all VPCs.
- IAM roles for cross-account RAM sharing.
- RDS: Non-public, with SG allowing TCP 5432 from Lattice-managed IPs.

#### **Account C: Networking (Service Network + RAM Share)**
Create a shared Service Network.

**`networking-account/main.tf`**:
```hcl
provider "aws" {
  alias  = "networking"
  region = "us-east-1"
}

# Service Network
module "vpc_lattice" {
  source  = "aws-ia/amazon-vpc-lattice-module/aws"
  version = "~> 0.1.0"  # Latest as of 2025

  create_service_network = true
  service_network_name   = "databricks-rds-lattice"
  service_network_tags = {
    Environment = "Production"
  }

  # RAM Sharing
  create_ram_share     = true
  ram_share_name       = "vpc-lattice-share"
  ram_principals       = ["arn:aws:iam::${var.rds_account_id}:root", "arn:aws:iam::${var.databricks_account_id}:root"]
  ram_share_tags = {
    Purpose = "Cross-Account RDS Access"
  }
}

variable "rds_account_id" { type = string }
variable "databricks_account_id" { type = string }
```

**Outputs: `networking-account/outputs.tf`**:
```hcl
output "service_network_arn" {
  value = module.vpc_lattice.service_network_arn
}

output "ram_share_arn" {
  value = module.vpc_lattice.ram_share_arn
}
```

---

#### **Account B: RDS Provider (Resource Gateway & Configuration)**
Expose RDS via a **Resource Gateway** (acts like a managed NLB for TCP) and **Resource Configuration** (ARN-based for RDS).

**`rds-account/main.tf`**:
```hcl
provider "aws" {
  alias  = "rds"
  region = "us-east-1"
}

# Existing RDS (from previous guide)
module "rds" {
  source = "terraform-aws-modules/rds/aws"
  # ... (same as before: identifier="databricks-postgres", port=5432, etc.)
}

# Resource Gateway (in RDS VPC, private subnets)
resource "aws_vpc_lattice_resource_gateway" "rds_gateway" {
  name        = "rds-postgres-gateway"
  vpc_identifier = module.vpc.vpc_id  # RDS VPC
  subnet_ids  = module.vpc.private_subnets  # Private subnets

  security_group_ids = [aws_security_group.gateway_sg.id]

  tags = {
    Name = "rds-lattice-gateway"
  }
}

# Security Group for Gateway: Egress to RDS only
resource "aws_security_group" "gateway_sg" {
  name_prefix = "lattice-gateway-"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.rds.security_group_ids[0]]  # RDS SG
  }

  # Allow health checks from Lattice
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true  # Or Lattice managed prefixes
  }
}

# Resource Configuration: Point to RDS ARN
resource "aws_vpc_lattice_resource_configuration" "rds_config" {
  name                            = "rds-postgres-config"
  resource_gateway_identifier     = aws_vpc_lattice_resource_gateway.rds_gateway.id
  allow_association_to_shareable_service_network = true
  type                            = "ARN"
  arn_resource {
    arn = module.rds.db_instance_arn
  }
}

# Associate to Shared Service Network (cross-account reference)
data "terraform_remote_state" "networking" {
  backend = "s3"
  config = {
    bucket = "networking-tf-state"
    key    = "vpc-lattice/terraform.tfstate"
    region = "us-east-1"
  }
}

resource "aws_vpc_lattice_service_network_resource_association" "rds_assoc" {
  resource_configuration_identifier = aws_vpc_lattice_resource_configuration.rds_config.id
  service_network_identifier        = data.terraform_remote_state.networking.outputs.service_network_arn
}
```

**RDS SG Update** (Allow ingress from Gateway SG):
```hcl
resource "aws_security_group_rule" "rds_from_lattice" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.rds.security_group_id
  source_security_group_id = aws_security_group.gateway_sg.id
}
```

**Outputs: `rds-account/outputs.tf`**:
```hcl
output "resource_config_id" {
  value = aws_vpc_lattice_resource_configuration.rds_config.id
}
```

**Accept RAM Share** (in RDS Account):
```hcl
# Principal Association (auto-accepted in Organizations)
resource "aws_ram_principal_association" "rds_ram" {
  principal          = data.aws_caller_identity.current.arn
  resource_share_arn = data.terraform_remote_state.networking.outputs.ram_share_arn
}
```

---

#### **Account A: Databricks Consumer (VPC Endpoint)**
Connect Databricks VPC to the shared Service Network.

**`databricks-account/main.tf`**:
```hcl
provider "aws" {
  alias  = "databricks"
  region = "us-east-1"
}

data "databricks_aws_workspace_conf" "this" {
  workspace_url = "https://your-workspace.cloud.databricks.com"
}

# VPC Endpoint to Shared Service Network
resource "aws_vpc_endpoint" "lattice_endpoint" {
  vpc_id              = data.databricks_aws_workspace_conf.this.root_vpc_id
  service_name        = data.terraform_remote_state.networking.outputs.service_network_arn  # Shared ARN
  vpc_endpoint_type   = "Interface"  # For Lattice
  subnet_ids          = data.databricks_aws_workspace_conf.this.private_subnet_ids
  security_group_ids  = [aws_security_group.endpoint_sg.id]
  private_dns_enabled = true

  tags = {
    Name = "databricks-lattice-endpoint"
  }
}

# Endpoint SG: Allow outbound TCP to RDS port
resource "aws_security_group" "endpoint_sg" {
  name_prefix = "lattice-endpoint-"
  vpc_id      = data.databricks_aws_workspace_conf.this.root_vpc_id

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.terraform_remote_state.rds.outputs.vpc_cidr]  # RDS VPC CIDR
  }
}

# Update Databricks Cluster SG (if custom)
resource "aws_security_group_rule" "databricks_to_lattice" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = data.databricks_aws_workspace_conf.this.cluster_security_group_id  # Or custom
  source_security_group_id = aws_security_group.endpoint_sg.id
}
```

**Accept RAM Share** (in Databricks Account):
```hcl
resource "aws_ram_principal_association" "databricks_ram" {
  principal          = data.aws_caller_identity.current.arn
  resource_share_arn = data.terraform_remote_state.networking.outputs.ram_share_arn
}
```

---

## 🛡️ **Ingress/Egress Summary Table**

| Component              | **Ingress** (Inbound)                          | **Egress** (Outbound)                          |
|------------------------|------------------------------------------------|------------------------------------------------|
| **RDS PostgreSQL**     | ✅ TCP 5432 from **Resource Gateway SG**       | ✅ All (`0.0.0.0/0`)                           |
| **Resource Gateway**   | ✅ Health checks from Lattice (self)           | ✅ TCP 5432 to **RDS SG**                      |
| **Service Network**    | N/A (logical)                                  | N/A                                            |
| **VPC Endpoint (Databricks)** | N/A (managed)                              | ✅ TCP 5432 via Lattice to RDS                 |
| **Databricks Clusters**| N/A                                            | ✅ TCP 5432 to **Endpoint SG** / RDS CIDR      |

---

## 🚀 **Deployment Steps**
1. **Deploy Networking Account First**: `terraform apply` → Note `service_network_arn` & `ram_share_arn`.
2. **Deploy RDS Account**: Reference Networking state, accept RAM share.
3. **Deploy Databricks Account**: Reference Networking, accept RAM share.
4. **Test Connectivity** (from Databricks Notebook):
   ```python
   import psycopg2
   conn = psycopg2.connect(
       host="your-rds-endpoint.region.rds.amazonaws.com",  # Resolves via private DNS
       port=5432,
       dbname="yourdb",
       user="admin",
       password="SecurePass123!"
   )
   print("Connected!")
   ```
5. **Monitor**: Use VPC Lattice metrics in CloudWatch (e.g., `ActiveConnections`, `BytesProcessed`).

## ⚠️ **Best Practices & Notes**
- **RAM Setup**: Enable AWS Organizations for auto-accept; otherwise, manually accept shares in console.
- **DNS**: Private DNS resolves RDS endpoint via Lattice – no public exposure.
- **Auth for TCP**: Relies on SGs/NACLs; for HTTP services, add IAMAuthPolicy.
- **Databricks Integration**: Clusters use VPC endpoint for outbound; ensure cluster SG allows Lattice traffic.
- **Cleanup Order**: Endpoints → Associations → Resources → Shares → Network.
- **Docs**: [AWS VPC Lattice User Guide](https://docs.aws.amazon.com/vpc/latest/lattice/what-is-vpc-lattice.html), [Terraform Module](https://github.com/aws-ia/terraform-aws-amazon-vpc-lattice-module).
- **Compared to PrivateLink**: Lattice is simpler for multiple services; PrivateLink better for single endpoints.

Need **full repo**, **EKS adaptation**, or **cost calculator**? Let me know! 🚀
CREATE TABLE dbo.Sales (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    TransactionDate DATETIME NOT NULL,
    Amount DECIMAL(10, 2) NOT NULL,
    CustomerID INT NULL,
    ProductID INT NULL,
    Quantity INT NOT NULL DEFAULT 1,
    Notes NVARCHAR(255) NULL
);
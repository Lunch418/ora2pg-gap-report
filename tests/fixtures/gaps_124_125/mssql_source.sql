CREATE TABLE [dbo].[Orders](
    [Id] [int] NOT NULL,
    [Total] [int] NULL,
 CONSTRAINT [PK_Orders] PRIMARY KEY CLUSTERED ([Id] ASC)
);
GO
CREATE VIEW [dbo].[BigOrders] AS SELECT [Id] FROM [dbo].[Orders] WHERE [Total] > 100;
GO
CREATE PROCEDURE [dbo].[CountOrders]
AS
BEGIN
    SELECT COUNT(*) FROM [dbo].[Orders];
END
GO

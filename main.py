import numpy as np

class QuantumVentralReplicator(QCAlgorithm):

    def Initialize(self):
        
        #Initial cash amount 
        self.SetCash(100000)
        
        #Algorithm start date (for backtesting)
        self.SetStartDate(2010, 2, 1)
        
        #Algorithm end date (for backtesting)
        self.SetEndDate(2021, 4, 1)
        
        #We are going to use daily data  to trade it
        self.symbol = self.AddEquity("WMT", Resolution.Daily).Symbol
        
        #This is the amount of days that we're going to lookback to determine the breakout point
        #We are going to change this dynamically based on changes in volatility
        self.lookback = 20
        
        #We still need to add some contraints to the lookback length because we dont want it to be too big or too small
        self.ceiling, self.floor = 30, 5
        
        #This is the first part of our trailing stop loss
        #This indicates how close our first stop loss will be to the price of the security, 
        #0.98 will allow for a 2% loss before the stop loss is hit
        self.initialStopRisk = 0.95
        
        #This indicates how close our trailing stop will follow the price, 0.9 means the stop loss will trail the price by 10%
        self.trailingStopRisk = 0.8
        
        
        #We will schedual our trades 
        #The first argument is which day our security trades, we want to trade every day our security trades
        #The next parameter specifies which time our method is called, we call it 20 minutes after market open
        #The last parameter is which method is called, we call the EveryMarketOpen method 
        self.Schedule.On(self.DateRules.EveryDay(self.symbol), \
                        self.TimeRules.AfterMarketOpen(self.symbol, 20), \
                        Action(self.EveryMarketOpen))
        

    #The OnData method is called every time the algo recieves new data
    def OnData(self, data):
        #We will create a plot of the price of the security we want to trade
        #Plot takes three agruments, the name of the chart, the ticker of the security, and the actual data of the security
        self.Plot("Data Chart", self.symbol, self.Securities[self.symbol].Close)
        
    #This will be the method that will do the trading, it will be called at every market open hence the name   
    def EveryMarketOpen(self):
        
        #First thing we need to do is determine the lookback length for our breakout
        #For that we will look at 30 day volatility of the present day and compare it with yesterdays value
        
        #We get the closing price for the last 31 days
        close = self.History(self.symbol, 31, Resolution.Daily)["close"]
        
        #We calculate the volatility by taking the standard deviation of the closing price of over the past 30 days
        #We first do this for the current day 
        todayvol = np.std(close[1:31])
        
        #And then for the day before that
        yesterdayvol = np.std(close[0:30])
        
        
        #We now take the normalized value of these
        deltavol = (todayvol - yesterdayvol) / todayvol
        
        #We now multiply the current lookback length by deltavol + 1, 
        #so that our lookback length increases when volatility increases and vice versa
        self.lookback = round(self.lookback * (1 + deltavol))
        
        
        #We check if the lookback length is within our limits
        if self.lookback > self.ceiling:
            self.lookback = self.ceiling
        elif self.lookback < self.floor:
            self.lookback = self.floor
            
            
        #Check if a breakout is happening
        #We get a list of all daily price highs within our lookback length
        self.high = self.History(self.symbol, self.lookback, Resolution.Daily)["high"]
        
        #We check if we already have a postion
        #We check if the last closing price is higher that the highest high from self.high
        #We leave out the last data point of self.high because we dont want to compare yesterdays high with yesterdays lows
        if not self.Securities[self.symbol].Invested and \
                    self.Securities[self.symbol].Close >= max(self.high[:-1]):
                
            #This will buy the stock at the market price with 100% of our portfolio
            self.SetHoldings(self.symbol, 1)
                
            #we set the breakout level to this variable
            self.breakoutlvl = max(self.high[:-1])
                
            #We set the highest price to that variable
            self.highestPrice = self.breakoutlvl
                
        
        #Check if we have an open position
        if self.Securities[self.symbol].Invested:
            
            #Get the open orders for the security, if have not done so already
            if not self.Transactions.GetOpenOrders(self.symbol):
                
                #We send a stop loss order, we will sell our entire quantity of shares hench the -, to get our stop loss price,
                #We multiply our breakout level by the initial stop risk which gives us a risk of 2%
                self.stopMarketTicket = self.StopMarketOrder(self.symbol, \
                                        -self.Portfolio[self.symbol].Quantity, \
                                        self.initialStopRisk * self.breakoutlvl)
                                        
                                        
                                        
            #Check if a new high was made and check if the stop price is still less than the trailing stop                            
            if self.Securities[self.symbol].Close > self.highestPrice and \
                    self.initialStopRisk * self.breakoutlvl < self.Securities[self.symbol].Close * self.trailingStopRisk:
                    
                #Set the highest price to the latest closing price
                self.highestPrice = self.Securities[self.symbol].Close
                    
                #Create an UpdateOrderFields object
                updateFields = UpdateOrderFields()
                    
                #Update the order price of the stop loss so it rises with the securities price
                updateFields.StopPrice = self.Securities[self.symbol].Close * self.trailingStopRisk
                    
                #Update the existing stop loss order
                self.stopMarketTicket.Update(updateFields)
                    
                #Print the new stop price to the console
                self.Debug(updateFields.StopPrice)
                    
            #Plot the stop price to our plot
            self.Plot("Data Chart", "Stop Price", self.stopMarketTicket.Get(OrderField.StopPrice))
        
import time
import MetaTrader5 as mt5
 
# MetaTrader 5パッケージについてのデータを表示する
print("MetaTrader5 package author: ", mt5.__author__)
print("MetaTrader5 package version: ", mt5.__version__)
 
# MetaTrader 5ターミナルとの接続を確立する
if not mt5.initialize():
    print("initialize() failed, error code =",mt5.last_error())
    

# 買いリクエスト構造体を準備する
symbol = "NIKKEI"
symbol_info = mt5.symbol_info(symbol)
if symbol_info is None:
    print(symbol, "not found, can not call order_check()")
    mt5.shutdown()
    

# 銘柄が「気配値表示」似ない場合は追加する
if not symbol_info.visible:
    print(symbol, "is not visible, trying to switch on")
    if not mt5.symbol_select(symbol,True):
        print("symbol_select({}}) failed, exit",symbol)
        mt5.shutdown()
        
 
lot = 0.1
point = mt5.symbol_info(symbol).point
price = mt5.symbol_info_tick(symbol).ask
deviation = 20
request = {
  "action": mt5.TRADE_ACTION_DEAL,
  "symbol": symbol,
  "volume": lot,
  "type": mt5.ORDER_TYPE_BUY,
  "price": price,
  "sl": price - 100 * point,
  "tp": price + 100 * point,
  "deviation": deviation,
  "magic": 234000,
  "comment": "python script open",
  "type_time": mt5.ORDER_TIME_GTC,
  "type_filling": mt5.ORDER_FILLING_IOC #ORDER_FILLING_RETURN,
}
 
# 取引リクエストを送信する
result = mt5.order_send(request)
print(request)
print(result)


# 実行結果を確認する
print("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol,lot,price,deviation));
if result.retcode != mt5.TRADE_RETCODE_DONE:
    print("2. order_send failed, retcode={}".format(result.retcode))
    # 結果をディクショナリとしてリクエストし、要素ごとに表示する
    result_dict=result._asdict()
    for field in result_dict.keys():
        print("   {}={}".format(field,result_dict[field]))
        # これが取引リクエスト構造体の場合は要素ごとに表示する
        if field=="request":
            traderequest_dict=result_dict[field]._asdict()
            for tradereq_filed in traderequest_dict:
                print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))
    print("shutdown() and quit")
    mt5.shutdown()
  
 
print("2. order_send done, ", result)
print("   opened position with POSITION_TICKET={}".format(result.order))
print("   sleep 2 seconds before closing position #{}".format(result.order))
time.sleep(2)
# 決済リクエストを作成する
position_id=result.order
price=mt5.symbol_info_tick(symbol).bid
deviation=20
request={
  "action": mt5.TRADE_ACTION_DEAL,
  "symbol": symbol,
  "volume": lot,
  "type": mt5.ORDER_TYPE_SELL,
  "position": position_id,
  "price": price,
  "deviation": deviation,
  "magic": 234000,
  "comment": "python script close",
  "type_time": mt5.ORDER_TIME_GTC,
  "type_filling": mt5.ORDER_FILLING_RETURN,
}
# 取引リクエストを送信する
result=mt5.order_send(request)
# 実行結果を確認する
print("3. close position #{}: sell {} {} lots at {} with deviation={} points".format(position_id,symbol,lot,price,deviation));
if result.retcode != mt5.TRADE_RETCODE_DONE:
    print("4. order_send failed, retcode={}".format(result.retcode))
    print("   result",result)
else:
    print("4. position #{} closed, {}".format(position_id,result))
    # 結果をディクショナリとしてリクエストし、要素ごとに表示する
    result_dict=result._asdict()
    for field in result_dict.keys():
        print("   {}={}".format(field,result_dict[field]))
        # これが取引リクエスト構造体の場合は要素ごとに表示する
        if field=="request":
            traderequest_dict=result_dict[field]._asdict()
            for tradereq_filed in traderequest_dict:
                print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))

# MetaTrader 5ターミナルへの接続をシャットダウンする
mt5.shutdown()
 
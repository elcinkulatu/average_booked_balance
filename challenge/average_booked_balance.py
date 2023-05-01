import pandas

pandas.set_option("display.precision", 7)


def average_booked_balance_from(transactions: pandas.DataFrame,
                                accounts: pandas.DataFrame,
                                reference_timestamps: pandas.DataFrame) -> pandas.Series:
    """
    :param transactions: pandas dataframe containing the transactions from a collection of accounts
    :param accounts: pandas dataframe containing a collection of accounts together with their balance when they
        were first added to our systems.
    :param reference_timestamps: pandas dataframe with the ref_timestamp a which to compute the average booked balance for
        each account. Different account might have different reference timestamps.
    :return:
        a pandas series where the index is a multindex containing the reference ref_timestamp and the account id, and the
        values are the average booked balances, e.g

        index                               | value
        ('2022-01-12 23:59:59.999', 'ac_1') | 12.3
        ('2022-03-10 23:59:59.999', 'ac_2') | 26.8
    """
    # timestamps conversion into datetime and sorting records by timestamps
    reference_timestamps["reference_timestamp"] = pandas.to_datetime(reference_timestamps["reference_timestamp"])
    accounts["creation_timestamp"] = pandas.to_datetime(accounts["creation_timestamp"])
    accounts.sort_values(by="creation_timestamp", inplace=True)
    transactions["value_timestamp"] = pandas.to_datetime(transactions["value_timestamp"])
    transactions.sort_values(by="value_timestamp", inplace=True)

    reference_timestamps["average_booked_balance"] = reference_timestamps.apply(
        lambda row: calculate_avg_bb(transactions, accounts, row), axis=1)

    reference_timestamps["reference_timestamp"] = reference_timestamps["reference_timestamp"].astype(str)
    result = reference_timestamps.set_index(["reference_timestamp", "account_id"])["average_booked_balance"]
    return result


def calculate_avg_bb(transactions: pandas.DataFrame, accounts: pandas.DataFrame, row: pandas.Series) -> float:
    """Calculates the average booked balance of an account

    :param transactions: pandas dataframe containing the transactions from a collection of accounts
    :param accounts: pandas dataframe containing a collection of accounts together with their balance when they
        were first added to our systems.
    :param row: a row of a pandas dataframe with the ref_timestamp and account_id information
    :return:
        the average booked balance value of the row
    """
    acc_id = row["account_id"]
    ref_timestamp = row["reference_timestamp"]
    start_timestamp = ref_timestamp - pandas.DateOffset(days=90)
    creation_info = accounts[accounts["account_id"] == acc_id]
    if len(creation_info) == 0:
        # no account exists, we cannot calculate the result
        return 0

    # if more than one balance record, consider the latest one
    creation_info = creation_info.tail(1)
    latest_info_timestamp = creation_info["creation_timestamp"].squeeze()

    # find the balance at the start_timestamp
    start_balance = creation_info["balance_at_creation"].squeeze()

    # case 1: latest info (creation time) before start_timestamp. therefore we need to calculate the balance on
    # start_timestamp
    transactions_subset = transactions[transactions["account_id"] == acc_id]
    if latest_info_timestamp < start_timestamp:
        diff = find_diff_btw_dates(latest_info_timestamp, start_timestamp, transactions_subset)
        start_balance += diff

    # case 2: latest info (creation time) later than start_timestamp. we need to go back in time to know the
    # starting balance
    elif start_timestamp < latest_info_timestamp:
        diff = find_diff_btw_dates(start_timestamp, latest_info_timestamp, transactions_subset)
        start_balance -= diff

    # now, filter the transactions to calculate the average
    transaction_window = transactions_subset[(transactions_subset["value_timestamp"] >= start_timestamp) &
                                             (transactions_subset["value_timestamp"] <= ref_timestamp)]
    # no transactions found. the average booked balance equals to the start balance
    if len(transaction_window) == 0:
        return start_balance

    # if the first transaction coincides with the start_timestamp, change its amount to 0 because we already counted
    # that amount when calculating start_balance
    if transaction_window["value_timestamp"].values[0] == start_timestamp:
        transaction_window.loc[0, "amount"] = 0

    # shift the dates based on the time of the day of start_timestamp. e.g. if we start on date YYYY-mm-dd 21.30,
    # then add 2.5 hours to each transaction timestamp, so that when we group by the date later, the transactions made
    # before 21.30 and after 21.30 will be separated in different days
    tomorrow = start_timestamp.date() + pandas.DateOffset(days=1)
    delta = tomorrow - start_timestamp  # the remaining time until tomorrow
    transaction_window["dummy_timestamp"] = transaction_window["value_timestamp"] + delta
    transaction_window["dummy_timestamp"] = transaction_window["dummy_timestamp"].dt.date

    # fill in the missing days (days without any transactions)
    dates = pandas.DataFrame({"dummy_timestamp": pandas.date_range(tomorrow, ref_timestamp)})
    transaction_window["dummy_timestamp"] = transaction_window["dummy_timestamp"].astype('datetime64[ns]')
    transaction_window = transaction_window.merge(dates, on="dummy_timestamp", how="outer")

    # put 0 as amount for the missing days
    transaction_window["amount"] = transaction_window["amount"].fillna(0)

    # sum the transactions per each day
    transaction_window = pandas.DataFrame(transaction_window.groupby("dummy_timestamp").amount.sum())
    # return the mean of the cumulative sum + start_balance
    return transaction_window["amount"].cumsum().mean() + start_balance


def find_diff_btw_dates(start_date: pandas.Timestamp, end_date: pandas.Timestamp,
                        transactions: pandas.DataFrame) -> float:
    """Finds the difference in amount between two dates based on the transactions
    :param start_date start timestamp of the transactions (not inclusive)
    :param end_date start timestamp of the transactions  (inclusive)
    :param transactions: pandas dataframe containing the transactions from a collection of accounts

    :return:
        sum of all transactions between start_date and end_date

    """
    transactions_subset = transactions[(start_date < transactions["value_timestamp"]) &
                                       (transactions["value_timestamp"] <= end_date)]
    return transactions_subset["amount"].sum()

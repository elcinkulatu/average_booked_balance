# Average Booked Balance Computation

## Challenge 
Imagine you’re working for a fintech company that collects information from 
bank accounts of people. The company wants to implement a new function that
computes the average balance for a collection of accounts , and it 
provides you with the following datasets:

* a dataset containing all the transactions currently in possession for 
  some bank accounts. The avaliable fields are the id of the account 
  to which each transaction pertains (`account_id`), the moment at 
  which each transaction was made (`value_timestamp`), and the amount 
  of the transaction (`amount`).
* a dataset containing information about the bank accounts. The available
  fields here are the id of each account (`account_id`), the time at 
  which that account was created in the company systems (`creation_timestamp`),
  and the account balance value at `creation_timestamp`
* a dataset that specifies for each account at which date to compute the 
  average balance. The fields here are the id of the account to consider
  (`account_id`), and the time at which the result is required for each
  account (`reference_timestamp`).

Your task is to build the function that, for each account, computes the average
value of the over the 90 days before the `reference_timestamp`, i.e.

```math
\mbox{average\_booked\_balance} = \frac{\sum_{\mbox{day} \in D} \mbox{balance}_\mbox{day}}{90}
```

where

```math
D = \{\mbox{days between (reference\_timestamp - 90days) and (reference\_timestamp)}\}
```

For example if we have

| account_id | reference_timestamp     |
|------------|-------------------------|
| ac_1       | 2017-03-31 23:59:59.999 |
| ac_2       | 2017-04-15 23:59:59.999 |

the function should return:
* the average value of the balance observed each day between 
  `2016-12-31 23:59:59.999` and `2017-03-31 23:59:59.999` for `ac_1`
* the average value of the balance observed each day between
  `2017-01-15 23:59:59.999` and `2017-04-15 23:59:59.999` for `ac_2`.

Multiple factors contributes to the overall difficulty of the challenge, such as

1. For each account the balance is known only at the `creation_timestamp`, so
   the balance at other days have to be computed using the transactions.
2. If a day has more than one transaction, one has to decide at which time 
   compute the balance for that date.
3. Some accounts do not have transactions for a long period of time, and this
   should be reflected in the average booked balance result.
4. `creation_timestamp` can be either before or after the `reference_timestamp`.
5. Different accounts can have different `reference_timestemp` values. 


## Solution

The solution can be found in `challenge/average_booked_balance.py`. The idea is to find the 
balance 90 days prior to `reference_timestamp`, then calculate the daily average of the
transactions between these two dates. The overall average booked balance equals the sum of 
the starting balance & this average over 90 days.
We iterate the queries one by one and for each query:

* Use the accounts information to find the balance at the creation time. Note that if there are
multiple records related to an account, only the latest one will be considered. If there is
no creation information, the average booked balance is assumed to be zero. Another assumption
is that the creation timestamp cannot coincide with a transaction.
* Set the `start_timestamp`, the starting date of the calculation, as exactly 90 days 
before the `reference_timestamp`.
* If `start_timestamp` is not equal to `reference_timestamp`, sum up all the transactions 
between these two dates. If `start_timestamp` comes before, subtract this amount from the 
balance at the creation time to go back in time. If `start_timestamp` comes later, we add 
the difference to the starting balance.
* The time of the day of the query is important. For example, imagine that the `start_timestamp` 
is YYYY-mm-dd 21.30. We need a way to group the transactions so that for each day, the transactions
made before and after 21.30 fall into two seperate groups. To achieve that, we create a 
`dummy_timestamp` which is a shifted version of the transaction timestamp. We calculate it by
adding 1.5 hours to the `reference_timestamp`, which is the remaining time from 21.30 until 
the next day. 
* Create a null transaction for each missing day for `dummy_timestamp`.
* Sum the transaction amounts per day and calculate the cumulative sum's average.

The most important assumption that I made here is that the `creation_timestamp` does not actually
mean that the account was created at that time. It only indicates a specific time instance that we 
receive the knowledge of the balance of an account. In other words, if we receive this information 
after our reference (or start) timestamp, it does not mean that this account did not exist at that 
time, we just had not received the balance information yet. We recover this by going back in time
based on the transactions.
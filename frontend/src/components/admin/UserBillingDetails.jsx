const value = (item) => item === null || item === undefined || item === '' ? 'Not available' : item;
const date = (item) => item ? new Date(item.endsWith('Z') ? item : `${item}Z`).toLocaleString() : 'Not available';

export default function UserBillingDetails({ subscription, payments, onPaymentPage }) {
 return <>
  <h3>Subscription and credits</h3>
  <dl className="account-details">
   <div><dt>Plan</dt><dd>{value(subscription?.plan)}</dd></div>
   <div><dt>Subscription status</dt><dd>{value(subscription?.status)}</dd></div>
   <div><dt>Total allocated credits · current period</dt><dd>{value(subscription?.allocated)}</dd></div>
   <div><dt>Used credits · current period</dt><dd>{value(subscription?.used)}</dd></div>
   <div><dt>Remaining credits</dt><dd>{value(subscription?.remaining)}</dd></div>
   <div><dt>Credit period ends</dt><dd>{date(subscription?.period_end)}</dd></div>
   <div><dt>Subscription expiry</dt><dd>{date(subscription?.end_date)}</dd></div>
   {subscription?.allowance_status && <div><dt>One-time generation allowance</dt><dd>{subscription.allowance_status.replaceAll('_',' ')}</dd></div>}
  </dl>
  {subscription?.note && <p>{subscription.note}</p>}
  <h3>Payment history</h3>
  {!payments?.available ? <p>Not available</p> : payments.total === 0 ? <p>No payment history</p> : <>
   <p>Currency, payment method and gateway transaction ID are not recorded by the current payment system.</p>
   {payments.items.length === 0 && <p>No payments on this page.</p>}
   {payments.items.map(payment => <article className="account-card" key={payment.record_id}>
    <dl className="account-details">
     <div><dt>Payment record ID</dt><dd>{payment.record_id}</dd></div>
     <div><dt>Transaction ID</dt><dd>{value(payment.transaction_id)}</dd></div>
     <div><dt>Payment date</dt><dd>{date(payment.date)}</dd></div>
     <div><dt>Amount</dt><dd>{value(payment.amount)}</dd></div>
     <div><dt>Currency</dt><dd>{value(payment.currency)}</dd></div>
     <div><dt>Payment method</dt><dd>{value(payment.method)}</dd></div>
     <div><dt>Plan</dt><dd>{value(payment.plan)}</dd></div>
     <div><dt>Payment status</dt><dd>{value(payment.status)}</dd></div>
    </dl>
   </article>)}
   <p>{payments.total} payments · Page {payments.page}</p>
   <button className="account-secondary" disabled={payments.page <= 1} onClick={()=>onPaymentPage(payments.page-1)}>Previous payments</button>
   <button className="account-secondary" disabled={payments.page*payments.page_size >= payments.total} onClick={()=>onPaymentPage(payments.page+1)}>Next payments</button>
  </>}
 </>;
}
